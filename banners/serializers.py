from rest_framework import serializers
from .models import Banner
from orders.models import Coupon  # Adjust if located elsewhere

class BannerSerializer(serializers.ModelSerializer):
    coupon_code = serializers.CharField(source='coupon.code', read_only=True)

    class Meta:
        model = Banner
        fields = [
            'id', 'title', 'subtitle', 'discount_text',
            'coupon', 'coupon_code', 'image', 'is_active', 'order', 'created_at'
        ]
