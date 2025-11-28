from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AdminOrderStatsView,
    OrderViewSet,
    CartView,
    AddToCartView,
    RemoveCartItemView,
    UpdateOrderStatusView,
)

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename="orders")

urlpatterns = [
    # Order routes via ViewSet
    path("", include(router.urls)),

    # ---------------- CART ROUTES ----------------
    path("cart/", CartView.as_view(), name="cart-detail"),
    path("cart/add/", AddToCartView.as_view(), name="cart-add"),
    path("cart/remove/<int:product_id>/", RemoveCartItemView.as_view(), name="cart-remove"),

    # ---------------- ORDER MANAGEMENT (Admin Only) ----------------
    path("orders/<int:order_id>/status/", UpdateOrderStatusView.as_view(), name="order-status-update"),
    path("admin/stats/", AdminOrderStatsView.as_view(), name="admin-order-stats"),
]
