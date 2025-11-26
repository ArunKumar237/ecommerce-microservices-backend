from rest_framework import generics, status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

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

            # deduct inventory
            item.product.inventory -= item.quantity
            item.product.save()

        # clear cart
        cart.items.all().delete()

        return Response(OrderSerializer(order).data, status=201)
