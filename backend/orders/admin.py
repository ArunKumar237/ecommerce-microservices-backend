from django.contrib import admin
from .models import Cart, CartItem, Order, OrderItem

for model in (Cart, CartItem, Order, OrderItem):
    attrs = {
        'list_display': [f.name for f in model._meta.fields],
    }
    admin.site.register(model, type(f'{model.__name__}Admin', (admin.ModelAdmin,), attrs))
