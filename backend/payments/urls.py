from django.urls import path
from .views import CreateRazorpayOrder, VerifyRazorpayPayment, RazorpayWebhookView, RefundOrderView

urlpatterns = [
    path("razorpay/create-order/", CreateRazorpayOrder.as_view()),
    path("razorpay/verify/", VerifyRazorpayPayment.as_view()),
    path("razorpay/webhook/", RazorpayWebhookView.as_view()),
    path("razorpay/refund/<int:order_id>/", RefundOrderView.as_view()),
]
