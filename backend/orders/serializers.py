from rest_framework import serializers
from .models import Cart, CartItem, Order, OrderItem
from products.serializers import ProductListSerializer
from products.models import Product


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), write_only=True, source="product"
    )

    class Meta:
        model = CartItem
        fields = ("id", "product", "product_id", "quantity", "subtotal")


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ("id", "items", "total")

    def get_total(self, obj):
        return obj.total_amount()


class AddToCartSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "product", "quantity", "price_at_purchase", "subtotal")


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ("id", "status", "total_amount", "created_at", "items")
