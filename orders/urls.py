# orders/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, CheckoutView, generate_coupon, list_active_coupons, OrderPreviewView, stripe_webhook

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')

urlpatterns = [
    path('', include(router.urls)),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('preview/', OrderPreviewView.as_view(), name='order-preview'),
    path('generate-coupon/', generate_coupon, name='generate-coupon'),
    path('coupons/', list_active_coupons, name='list-active-coupons'),
    path('webhooks/stripe/', stripe_webhook, name='stripe-webhook'),  # New webhook endpoint
]