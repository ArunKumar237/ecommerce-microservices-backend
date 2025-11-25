from django.urls import path
from . import views

urlpatterns = [
    path("", views.ping, name="orders-ping"),
]
