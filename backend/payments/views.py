import hmac, hashlib
import logging
import razorpay

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from django.conf import settings
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from orders.models import Order
from orders.tasks import send_order_confirmation_email, generate_and_email_invoice
from .razorpay_service import client

logger = logging.getLogger(__name__)


class CreateRazorpayOrder(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        ip = request.META.get("REMOTE_ADDR")
        logger.info("[Razorpay] CreateOrder invoked by user=%s IP=%s", user.id, ip)

        order_id = request.data.get("order_id")

        try:
            order = Order.objects.get(id=order_id, user=user)
        except Order.DoesNotExist:
            logger.warning("[Razorpay] Order not found user=%s order_id=%s", user.id, order_id)
            return Response({"error": "Order not found"}, status=404)

        try:
            razorpay_order = client.order.create({
                "amount": int(order.total_amount * 100),
                "currency": "INR",
                "receipt": f"order_rcpt_{order.id}",
                "notes": {"order_id": order.id, "user_id": user.id}
            })

            logger.info("[Razorpay] Order created successfully razorpay_order_id=%s", razorpay_order["id"])

            return Response({
                "order_id": razorpay_order["id"],
                "key_id": settings.RAZORPAY_KEY_ID,
                "amount": int(order.total_amount * 100),
                "currency": "INR",
            })

        except Exception as e:
            logger.error("[Razorpay] ERROR creating order: %s", str(e), exc_info=True)
            return Response({"error": str(e)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class VerifyRazorpayPayment(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        user_ip = request.META.get("REMOTE_ADDR")

        logger.info("[Razorpay] VerifyPayment called IP=%s", user_ip)

        data = request.POST or request.data

        if not data.get("razorpay_order_id"):
            logger.debug("[Razorpay] VerifyPayment ignored (no razorpay_order_id)")
            return Response({"message": "ignored"}, status=200)

        try:
            client.utility.verify_payment_signature({
                "razorpay_order_id": data.get("razorpay_order_id"),
                "razorpay_payment_id": data.get("razorpay_payment_id"),
                "razorpay_signature": data.get("razorpay_signature"),
            })
            logger.info("[Razorpay] Signature verified")
        except razorpay.errors.SignatureVerificationError:
            logger.warning("[Razorpay] Signature verification FAILED for order=%s", data.get("razorpay_order_id"))
            return Response({"error": "Signature verification failed"}, status=400)

        try:
            rzp_order = client.order.fetch(data.get("razorpay_order_id"))
            order_id = rzp_order["notes"]["order_id"]
            user_id = rzp_order["notes"]["user_id"]

            order = Order.objects.get(id=order_id)

            if order.user_id != int(user_id):
                logger.warning("[Razorpay] Unauthorized payment attempt order=%s expected_user=%s", order_id, user_id)
                return Response({"error": "Unauthorized order claim"}, status=403)

            if order.status != "paid":
                for item in order.items.all():
                    item.product.inventory -= item.quantity
                    item.product.save()

                order.status = "paid"
                order.save()

                logger.info("[Razorpay] Order marked paid order=%s user=%s", order.id, user_id)

            return Response({"status": "success"}, status=200)

        except Exception as e:
            logger.error("[Razorpay] ERROR verifying payment: %s", str(e), exc_info=True)
            return Response({"error": str(e)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class RazorpayWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        body = request.body.decode("utf-8")
        received_signature = request.headers.get("X-Razorpay-Signature")

        logger.info("[Webhook] Received event signature=%s", received_signature)

        generated_signature = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if generated_signature != received_signature:
            logger.warning("[Webhook] Invalid signature")
            return Response({"error": "Invalid signature"}, status=400)

        event = request.data.get("event")
        logger.info("[Webhook] Event received: %s", event)

        # -------- PAYMENT CAPTURE --------
        if event == "payment.captured":
            payment_data = request.data["payload"]["payment"]["entity"]
            razorpay_order_id = payment_data.get("order_id")

            rzp_order = client.order.fetch(razorpay_order_id)
            order_id = rzp_order["notes"]["order_id"]

            try:
                order = Order.objects.get(id=order_id)

                if order.status != "paid":
                    for item in order.items.all():
                        item.product.inventory -= item.quantity
                        item.product.save()

                    order.status = "paid"
                    order.paid_at = timezone.now()
                    order.razorpay_order_id = razorpay_order_id
                    order.razorpay_payment_id = payment_data.get("id")
                    order.save()

                    send_order_confirmation_email.delay(order.id)
                    generate_and_email_invoice.delay(order.id)

                logger.info("[Webhook] Order paid order_id=%s", order_id)
                return Response({"message": "Order updated"}, status=200)

            except Order.DoesNotExist:
                logger.error("[Webhook] Order not found id=%s", order_id)
                return Response({"error": "Order not found"}, status=404)

        # -------- REFUND HANDLING --------
        elif event == "refund.processed":
            refund_data = request.data["payload"]["refund"]["entity"]
            payment_id = refund_data.get("payment_id")

            try:
                order = Order.objects.get(razorpay_payment_id=payment_id)
                order.status = "refunded"
                order.save()

                logger.info("[Webhook] Order refunded order_id=%s", order.id)
                return Response({"message": "Order marked refunded"}, status=200)

            except Order.DoesNotExist:
                logger.error("[Webhook] No order found for refund payment_id=%s", payment_id)
                return Response({"error": "Order not found"}, status=404)

        return Response({"message": "Ignored event"}, status=200)


class RefundOrderView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, order_id):
        user = request.user
        logger.info("[Admin Refund] Attempt by admin=%s for order=%s", user.id, order_id)

        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            logger.warning("[Admin Refund] Order not found id=%s", order_id)
            return Response({"error": "Order not found"}, status=404)

        if order.status not in ["paid", "shipped"]:
            logger.warning("[Admin Refund] Invalid refund state order=%s status=%s", order_id, order.status)
            return Response({"error": "Refund not allowed"}, status=400)

        if not order.razorpay_payment_id:
            logger.error("[Admin Refund] No payment ID for order=%s", order_id)
            return Response({"error": "No payment ID stored"}, status=400)

        try:
            refund = client.payment.refund({
                "payment_id": order.razorpay_payment_id,
                "amount": int(order.total_amount * 100),
            })
            logger.info("[Admin Refund] Refund initiated order=%s", order_id)

        except razorpay.errors.BadRequestError as e:
            logger.error("[Admin Refund] Razorpay refund failed: %s", str(e))
            return Response({"error": str(e)}, status=400)

        order.status = "refunded"
        order.save()

        return Response({"message": "Refund initiated", "refund": refund}, status=200)
