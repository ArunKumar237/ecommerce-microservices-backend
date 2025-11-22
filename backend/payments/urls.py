from django.urls import path
from . import views

urlpatterns = [
    path("payments/", views.ping, name="payments-ping"),
]
