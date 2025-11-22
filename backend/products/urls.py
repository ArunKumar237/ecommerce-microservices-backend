from django.urls import path
from . import views

urlpatterns = [
    path("products/", views.ping, name="products-ping"),
]
