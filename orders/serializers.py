from rest_framework import serializers
from .models import Order, OrderItem, Coupon
from products.serializers import ProductSerializer, ProductVariantSerializer
from django.contrib.auth import get_user_model
from django.utils import timezone  # NEW: Import timezone
import logging
from shipping.models import ShippingAddress
from shipping.serializers import ShippingAddressSerializer

logger = logging.getLogger(__name__)

User = get_user_model()

class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    variant = ProductVariantSerializer(read_only=True)
    class Meta:
        model = OrderItem
        fields = ['product', 'variant', 'quantity', 'price_at_purchase']

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    username = serializers.SerializerMethodField(read_only=True)
    coupon = serializers.CharField(write_only=True, required=False, allow_blank=True)
    shipping_address = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Order
        fields = [
            'order_id', 'user', 'username', 'status', 'total_price', 'discount_amount',
            'payment_status', 'payment_method', 'created_at', 'updated_at',
            'items', 'coupon', 'shipping_address'
        ]
        read_only_fields = [
            'order_id', 'user', 'username', 'created_at', 'updated_at',
            'total_price', 'items', 'discount_amount', 'shipping_address'
        ]

    def get_username(self, obj):
        return obj.user.username

    def get_shipping_address(self, obj):
        try:
            address = ShippingAddress.objects.get(order=obj)
            return ShippingAddressSerializer(address).data
        except ShippingAddress.DoesNotExist:
            return None

    def validate_coupon(self, value):
        if not value:
            logger.info("No coupon provided")
            return None
        try:
            coupon = Coupon.objects.get(code=value, is_active=True)
            if not coupon.is_valid():
                raise serializers.ValidationError("Coupon is expired or invalid.")
            return value
        except Coupon.DoesNotExist:
            raise serializers.ValidationError("Invalid coupon code.")

    def validate(self, data):
        data = super().validate(data)
        coupon_code = data.get('coupon', '')
        if coupon_code:
            try:
                data['coupon_obj'] = Coupon.objects.get(code=coupon_code, is_active=True)
                if not data['coupon_obj'].is_valid():
                    raise serializers.ValidationError("Coupon is expired or invalid.")
            except Coupon.DoesNotExist:
                raise serializers.ValidationError("Invalid coupon code.")
        else:
            data['coupon_obj'] = None
        return data
