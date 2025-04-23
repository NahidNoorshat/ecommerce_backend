from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet,
    ProductViewSet,
    ProductVariantViewSet,
    VariantAttributeViewSet,
    VariantAttributeValueViewSet,
    CartViewSet,
    BulkDeleteProductsView
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'products', ProductViewSet)
router.register(r'variants', ProductVariantViewSet)
router.register(r'variant-attributes', VariantAttributeViewSet)
router.register(r'variant-attribute-values', VariantAttributeValueViewSet)
router.register(r'cart', CartViewSet, basename='cart')

urlpatterns = [
    path('', include(router.urls)),
    path("bulk-delete/", BulkDeleteProductsView.as_view(), name="bulk-delete-products"),
]
