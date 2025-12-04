import logging
from rest_framework import generics, status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.views import APIView
from django.utils import timezone
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate

from orders.tasks import send_order_status_update_email
from products.models import Product
from .models import Cart, CartItem, Order, OrderItem
from .serializers import (
    CartSerializer,
    CartItemSerializer,
    AddToCartSerializer,
    OrderSerializer,
)

logger = logging.getLogger(__name__)


# -------- CART --------
class CartView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CartSerializer

    def get_object(self):
        user = self.request.user
        ip = self.request.META.get("REMOTE_ADDR")
        logger.info("[Cart] Fetch cart user=%s IP=%s", user.id, ip)

        cart, _ = Cart.objects.get_or_create(user=user)
        return cart


class AddToCartView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AddToCartSerializer

    def post(self, request, *args, **kwargs):
        user = request.user
        ip = request.META.get("REMOTE_ADDR")
        logger.info("[Cart] AddToCart user=%s IP=%s payload=%s", user.id, ip, request.data)

        cart, _ = Cart.objects.get_or_create(user=user)
        data = request.data

        try:
            product = Product.objects.get(id=data["product_id"])
        except Product.DoesNotExist:
            logger.warning("[Cart] Product not found user=%s product_id=%s", user.id, data.get("product_id"))
            return Response({"error": "Product not found"}, status=404)

        quantity = data.get("quantity", 1)

        item, created = CartItem.objects.get_or_create(cart=cart, product=product)
        item.quantity = item.quantity + quantity if not created else quantity
        item.save()

        logger.info("[Cart] Item added user=%s product_id=%s qty=%s", user.id, product.id, item.quantity)
        return Response({"message": "Added to cart"}, status=200)


class RemoveCartItemView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, product_id):
        user = request.user
        ip = request.META.get("REMOTE_ADDR")
        logger.info("[Cart] RemoveItem user=%s IP=%s product_id=%s", user.id, ip, product_id)

        cart, _ = Cart.objects.get_or_create(user=user)

        try:
            item = CartItem.objects.get(cart=cart, product_id=product_id)
        except CartItem.DoesNotExist:
            logger.warning("[Cart] Remove failed user=%s product_id=%s (not found)", user.id, product_id)
            return Response({"error": "Item not found in cart"}, status=404)

        item.delete()
        logger.info("[Cart] Item removed user=%s product_id=%s", user.id, product_id)
        return Response({"message": "Item removed"}, status=200)


# -------- ORDERS --------
class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        user = self.request.user
        logger.info("[Order] Fetch orders user=%s role=%s", user.id, user.role)
        return Order.objects.all() if user.role == "admin" else Order.objects.filter(user=user)

    def create(self, request, *args, **kwargs):
        user = request.user
        ip = request.META.get("REMOTE_ADDR")
        logger.info("[Order] CreateOrder user=%s IP=%s", user.id, ip)

        try:
            cart = Cart.objects.get(user=user)
        except Cart.DoesNotExist:
            logger.warning("[Order] Create failed (no cart) user=%s", user.id)
            return Response({"error": "Cart not found"}, status=404)

        if not cart.items.exists():
            logger.warning("[Order] Create failed (empty cart) user=%s", user.id)
            return Response({"error": "Cart is empty"}, status=400)

        total_amount = cart.total_amount()
        order = Order.objects.create(user=user, total_amount=total_amount)

        for item in cart.items.all():
            OrderItem.objects.create(order=order, product=item.product, quantity=item.quantity, price_at_purchase=item.product.price)

        cart.items.all().delete()

        logger.info("[Order] Order created user=%s order_id=%s total=%s", user.id, order.id, total_amount)
        return Response(OrderSerializer(order).data, status=201)


class UpdateOrderStatusView(APIView):
    permission_classes = [IsAdminUser]

    VALID_FLOW = {
        "pending": ["paid", "cancelled"],
        "paid": ["processing", "shipped", "cancelled"],
        "processing": ["shipped", "cancelled"],
        "shipped": ["delivered"],
        "delivered": [],
        "cancelled": [],
        "refunded": []
    }

    def patch(self, request, order_id):
        admin_user = request.user
        ip = request.META.get("REMOTE_ADDR")

        logger.info("[Order] StatusUpdate attempted admin=%s order_id=%s IP=%s payload=%s",
                    admin_user.id, order_id, ip, request.data)

        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            logger.error("[Order] StatusUpdate failed order not found id=%s", order_id)
            return Response({"error": "Order not found"}, status=404)

        new_status = request.data.get("status")

        if new_status not in dict(Order.STATUS_CHOICES):
            logger.warning("[Order] Invalid status selected admin=%s attempted=%s", admin_user.id, new_status)
            return Response({"error": "Invalid status"}, status=400)

        allowed_steps = self.VALID_FLOW.get(order.status, [])
        if new_status not in allowed_steps:
            logger.warning("[Order] Invalid transition admin=%s %s -> %s", admin_user.id, order.status, new_status)
            return Response(
                {"error": f"Invalid status transition: {order.status} → {new_status}"},
                status=400
            )

        # Extra metadata for shipping/delivery
        if new_status == "shipped":
            order.tracking_number = request.data.get("tracking_number")
            order.courier = request.data.get("courier")
            order.shipped_at = timezone.now()

        elif new_status == "delivered":
            order.delivered_at = timezone.now()

        order.status = new_status
        order.save()

        send_order_status_update_email.delay(order.id, order.status)

        logger.info("[Order] Status changed order_id=%s new_status=%s", order.id, new_status)

        return Response({"message": f"Order updated to {order.status}"}, status=200)


class AdminOrderStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        admin_user = request.user
        logger.info("[AdminStats] Stats requested by admin=%s", admin_user.id)

        qs = Order.objects.all()

        total_orders = qs.count()
        total_revenue = qs.filter(status__in=["paid", "shipped", "delivered", "refunded"]) \
                          .aggregate(total=Sum("total_amount"))["total"] or 0

        by_status = qs.values("status").annotate(count=Count("id")).order_by()

        last_7_days = (
            qs.filter(created_at__gte=timezone.now() - timezone.timedelta(days=7))
              .annotate(date=TruncDate("created_at"))
              .values("date")
              .annotate(count=Count("id"), revenue=Sum("total_amount"))
              .order_by("date")
        )

        logger.info("[AdminStats] Served for admin=%s", admin_user.id)

        return Response({
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "by_status": list(by_status),
            "last_7_days": list(last_7_days),
        })
