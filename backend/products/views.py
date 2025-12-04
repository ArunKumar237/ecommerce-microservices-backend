import logging
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
logger = logging.getLogger(__name__)


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
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUser()]
        return [IsAuthenticatedOrReadOnly()]

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        if self.action == "retrieve":
            return ProductDetailSerializer
        return ProductCreateUpdateSerializer

    def _log_request(self, action, extra=None):
        ip = self.request.META.get("REMOTE_ADDR")
        user = self.request.user if self.request.user.is_authenticated else "Anonymous"
        logger.info(
            f"[ProductViewSet] Action={action} User={user} IP={ip} {extra or ''}"
        )

    # Cached list
    @method_decorator(cache_page(CACHE_TTL))
    def list(self, request, *args, **kwargs):
        self._log_request("LIST PRODUCTS")
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        slug = kwargs.get("slug")
        cache_key = f"product_detail:{slug}"
        self._log_request("RETRIEVE PRODUCT", f"(slug={slug})")

        cached = cache.get(cache_key)
        if cached:
            logger.debug(f"[ProductViewSet] CACHE HIT for slug={slug}")
            return Response(cached)

        logger.debug(f"[ProductViewSet] CACHE MISS for slug={slug}")
        response = super().retrieve(request, *args, **kwargs)
        cache.set(cache_key, response.data, CACHE_TTL)
        return response

    def perform_create(self, serializer):
        instance = serializer.save()
        self._log_request("CREATE PRODUCT", f"(slug={instance.slug})")
        clear_product_caches()
        logger.debug("[ProductViewSet] Cache cleared after create")
        return instance

    def perform_update(self, serializer):
        instance = serializer.save()
        self._log_request("UPDATE PRODUCT", f"(slug={instance.slug})")
        clear_product_caches()
        logger.debug("[ProductViewSet] Cache cleared after update")
        return instance

    def perform_destroy(self, instance):
        self._log_request("DELETE PRODUCT", f"(slug={instance.slug})")
        instance.delete()
        clear_product_caches()
        logger.debug("[ProductViewSet] Cache cleared after delete")
