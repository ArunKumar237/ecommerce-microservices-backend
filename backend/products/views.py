from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from .cache_utils import clear_product_caches
from rest_framework import viewsets, status, filters
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAdminUser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .models import Product, Category
from .serializers import (
    ProductListSerializer,
    ProductDetailSerializer,
    ProductCreateUpdateSerializer,
    CategorySerializer,
)

CACHE_TTL = 60 * 5  # 5 minutes

class SmallResultsSetPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 100

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related("category").all()
    lookup_field = "slug"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "sku", "description"]
    ordering_fields = ["price", "created_at", "inventory"]
    pagination_class = SmallResultsSetPagination
    
    def get_permissions(self):
        # write operations → admin only
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUser()]
        # read operations → anyone
        return [IsAuthenticatedOrReadOnly()]

    def get_serializer_class(self):
        if self.action in ["list"]:
            return ProductListSerializer
        if self.action in ["retrieve"]:
            return ProductDetailSerializer
        return ProductCreateUpdateSerializer

    # Per-view caching for list
    @method_decorator(cache_page(CACHE_TTL))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        # low-level cache example for product detail
        slug = kwargs.get("slug")
        cache_key = f"product_detail:{slug}"
        data = cache.get(cache_key)
        if data:
            return Response(data)
        resp = super().retrieve(request, *args, **kwargs)
        cache.set(cache_key, resp.data, CACHE_TTL)
        return resp

    def perform_create(self, serializer):
        instance = serializer.save()
        # invalidate list cache when new product created
        clear_product_caches()
        return instance

    def perform_update(self, serializer):
        instance = serializer.save()
        clear_product_caches()
        return instance

    def perform_destroy(self, instance):
        instance.delete()
        clear_product_caches()
