from rest_framework import generics, status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from orders.tasks import send_order_status_update_email
from rest_framework.views import APIView
from django.utils import timezone
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate

from .models import Cart, CartItem, Order, OrderItem
from .serializers import (
    CartSerializer,
    CartItemSerializer,
    AddToCartSerializer,
    OrderSerializer,
)
from products.models import Product


# -------- CART --------
class CartView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CartSerializer

    def get_object(self):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return cart


class AddToCartView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AddToCartSerializer

    def post(self, request, *args, **kwargs):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        data = request.data

        product = Product.objects.get(id=data["product_id"])
        quantity = data.get("quantity", 1)

        item, created = CartItem.objects.get_or_create(cart=cart, product=product)
        if not created:
            item.quantity += quantity
        else:
            item.quantity = quantity
        item.save()

        return Response({"message": "Added to cart"}, status=200)


class RemoveCartItemView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, product_id):
        cart, _ = Cart.objects.get_or_create(user=request.user)

        try:
            item = CartItem.objects.get(cart=cart, product_id=product_id)
        except CartItem.DoesNotExist:
            return Response({"error": "Item not found in cart"}, status=404)

        item.delete()
        return Response({"message": "Item removed"}, status=200)



# -------- ORDERS --------
class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        if self.request.user.role == "admin":
            return Order.objects.all()
        return Order.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        cart = Cart.objects.get(user=request.user)
        if not cart.items.exists():
            return Response({"error": "Cart is empty"}, status=400)

        total_amount = cart.total_amount()
        order = Order.objects.create(user=request.user, total_amount=total_amount)

        for item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price_at_purchase=item.product.price,
            )
        
        # Clear the cart after creating order (optional — OR mark "locked")
        cart.items.all().delete()
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
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        new_status = request.data.get("status")

        if new_status not in dict(Order.STATUS_CHOICES):
            return Response({"error": "Invalid status"}, status=400)

        allowed_next_steps = self.VALID_FLOW.get(order.status, [])

        if new_status not in allowed_next_steps:
            return Response(
                {"error": f"Invalid status transition: {order.status} → {new_status}"},
                status=400
            )

        # Handle status updates
        if new_status == "shipped":
            order.tracking_number = request.data.get("tracking_number")
            order.courier = request.data.get("courier")
            order.shipped_at = timezone.now()

        elif new_status == "delivered":
            order.delivered_at = timezone.now()

        order.status = new_status
        order.save()

        send_order_status_update_email.delay(order.id, order.status)
        return Response({"message": f"Order updated to {order.status}"}, status=200)


class AdminOrderStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
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

        return Response({
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "by_status": list(by_status),
            "last_7_days": list(last_7_days),
        })