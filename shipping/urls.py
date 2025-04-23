# shipping/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ShippingAddressViewSet, ShippingMethodViewSet, mark_order_delivered

router = DefaultRouter()
router.register(r'addresses', ShippingAddressViewSet, basename='shipping-address')
router.register(r'methods', ShippingMethodViewSet, basename='shipping-method')

urlpatterns = [
    path('', include(router.urls)),
    path('orders/<str:order_id>/mark-delivered/', mark_order_delivered, name='mark-order-delivered'),
]