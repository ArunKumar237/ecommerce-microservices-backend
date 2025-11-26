from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import CartView, AddToCartView, RemoveCartItemView, OrderViewSet

router = DefaultRouter()
router.register("orders", OrderViewSet, basename="orders")

urlpatterns = [
    path("cart/", CartView.as_view()),
    path("cart/add/", AddToCartView.as_view()),
    path("cart/remove/<int:product_id>/", RemoveCartItemView.as_view()),
]

urlpatterns += router.urls
