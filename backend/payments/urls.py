from django.urls import path
from .views import CreateStripePaymentIntent, StripeWebhookView
from .views import CreateRazorpayOrder, VerifyRazorpayPayment, RazorpayWebhookView

urlpatterns = [
    path("create-intent/", CreateStripePaymentIntent.as_view()),
    path("webhook/", StripeWebhookView.as_view()),
    path("razorpay/create-order/", CreateRazorpayOrder.as_view()),
    path("razorpay/verify/", VerifyRazorpayPayment.as_view()),
    path("razorpay/webhook/", RazorpayWebhookView.as_view()),
]
