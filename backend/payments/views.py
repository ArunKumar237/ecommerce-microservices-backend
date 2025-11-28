import hmac, hashlib
import stripe, razorpay
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from orders.tasks import send_order_confirmation_email, generate_and_email_invoice
from django.conf import settings
from orders.models import Order
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

#---------------- STRIPE PAYMENT VIEWS -----------------------
stripe.api_key = settings.STRIPE_SECRET_KEY

class CreateStripePaymentIntent(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            order_id = request.data.get("order_id")
            order = Order.objects.get(id=order_id, user=request.user)

            intent = stripe.PaymentIntent.create(
                amount=int(order.total_amount * 100),   # Stripe uses cents
                currency="inr",
                metadata={"order_id": order.id},
            )

            return Response({"client_secret": intent["client_secret"]})

        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class StripeWebhookView(APIView):
    permission_classes = [AllowAny]  # Stripe calls without auth

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except Exception:
            return Response(status=400)

        # Handle payment success
        if event["type"] == "payment_intent.succeeded":
            payment_intent = event["data"]["object"]
            order_id = payment_intent["metadata"]["order_id"]

            Order.objects.filter(id=order_id).update(status="paid")

        return Response(status=200)


# -------------------razorpay views ------------------------
from .razorpay_service import client

class CreateRazorpayOrder(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            order_id = request.data.get("order_id")
            order = Order.objects.get(id=order_id)

            razorpay_order = client.order.create({
                "amount": int(order.total_amount * 100),
                "currency": "INR",
                "receipt": f"order_rcpt_{order.id}",
                "notes": {
                    "order_id": order.id, 
                    "user_id": request.user.id
                }
            })

            return Response({
                "order_id": razorpay_order["id"],
                "key_id": settings.RAZORPAY_KEY_ID,
                "amount": int(order.total_amount * 100),
                "currency": "INR",
            })

        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)
        
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

@method_decorator(csrf_exempt, name='dispatch')
class VerifyRazorpayPayment(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.POST or request.data

        if not data.get("razorpay_order_id"):
            return Response({"message": "ignored"}, status=200)
          
        # Log incoming payloads for debugging
        try:
            logger.info("VerifyRazorpayPayment invoked")
            logger.info("request.POST: %s", dict(request.POST))
            logger.info("request.data: %s", request.data)
            logger.info("request.body: %s", request.body.decode("utf-8", errors="replace"))
            logger.info("request.META.CONTENT_TYPE: %s", request.META.get("CONTENT_TYPE"))
            logger.info("request.META.HTTP_AUTHORIZATION: %s", request.META.get("HTTP_AUTHORIZATION"))
        except Exception as _e:
            logger.exception("Failed to log request payloads")
        try:
            client.utility.verify_payment_signature({
                "razorpay_order_id": data.get("razorpay_order_id"),
                "razorpay_payment_id": data.get("razorpay_payment_id"),
                "razorpay_signature": data.get("razorpay_signature"),
            })

            rzp_order = client.order.fetch(data.get("razorpay_order_id"))
            order_id = rzp_order["notes"]["order_id"]
            user_id = rzp_order["notes"]["user_id"]

            order = Order.objects.get(id=order_id)

            if order.user_id != int(user_id):
                return Response({"error": "Unauthorized order claim"}, status=403)

            if order.status != "paid":
                for item in order.items.all():
                    item.product.inventory -= item.quantity
                    item.product.save()
                order.status = "paid"
                order.save()

            return Response({"status": "success"}, status=200)

        except razorpay.errors.SignatureVerificationError:
            return Response({"error": "Signature verification failed"}, status=400)
        except Exception as e:
            return Response({"error": str(e)}, status=400)
        
# -------------- webhook to handle razorpay events --------------
@method_decorator(csrf_exempt, name='dispatch')
class RazorpayWebhookView(APIView):
    permission_classes = [AllowAny]  # Razorpay webhook has no auth

    def post(self, request):
        secret = settings.RAZORPAY_WEBHOOK_SECRET
        body = request.body.decode("utf-8")
        received_signature = request.headers.get("X-Razorpay-Signature")

        # Verify signature using HMAC
        generated_signature = hmac.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if generated_signature != received_signature:
            return Response({"error": "Invalid signature"}, status=400)

        payload = request.data
        event = payload.get("event")

        if event == "payment.captured":
            payment_data = payload["payload"]["payment"]["entity"]
            razorpay_order_id = payment_data.get("order_id")

            # Fetch metadata stored earlier
            rzp_order = client.order.fetch(razorpay_order_id)
            order_id = rzp_order["notes"]["order_id"]
            user_id = rzp_order["notes"]["user_id"]

            try:
                order = Order.objects.get(id=order_id)

                if order.status != "paid":
                    # Deduct stock only once
                    for item in order.items.all():
                        product = item.product
                        product.inventory -= item.quantity
                        product.save()

                    order.status = "paid"
                    order.paid_at = timezone.now()
                    order.razorpay_order_id = razorpay_order_id
                    order.razorpay_payment_id = payment_data.get("id")
                    order.save()

                    # background tasks
                    send_order_confirmation_email.delay(order.id)
                    generate_and_email_invoice.delay(order.id)

                return Response({"message": "Order updated"}, status=200)

            except Order.DoesNotExist:
                return Response({"error": "Order not found"}, status=404)
            
        elif event == "refund.processed":
            refund_data = payload["payload"]["refund"]["entity"]
            payment_id = refund_data.get("payment_id")

            try:
                order = Order.objects.get(razorpay_payment_id=payment_id)
            except Order.DoesNotExist:
                return Response({"error": "Order not found for refund"}, status=404)

            order.status = "refunded"
            order.save()

            return Response({"message": "Order marked as refunded"}, status=200)
        
        return Response({"message": "Ignored event"}, status=200)
    

class RefundOrderView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        if order.status not in ["paid", "shipped"]:
            return Response({"error": "Refund not allowed in this state"}, status=400)

        if not order.razorpay_payment_id:
            return Response({"error": "No payment id stored for this order"}, status=400)

        try:
            refund = client.payment.refund({
                "payment_id": order.razorpay_payment_id,
                "amount": int(order.total_amount * 100),
            })
        except razorpay.errors.BadRequestError as e:
            return Response({"error": str(e)}, status=400)

        # optional: mark as refunded here OR wait for webhook
        order.status = "refunded"
        order.save()

        return Response({"message": "Refund initiated", "refund": refund}, status=200)