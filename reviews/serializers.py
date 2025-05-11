# reviews/serializers.py

from rest_framework import serializers
from .models import Review
from orders.models import OrderItem, Order
from products.models import Product
from django.utils import timezone

class ReviewSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField(read_only=True)  # ✅ override display

    class Meta:
        model = Review
        fields = ["id", "product", "rating", "comment", "user", "created_at"]
        read_only_fields = ["user", "created_at"]

    def get_user(self, obj):
        return obj.user.username  # or obj.user.get_full_name() if available

    def validate(self, data):
        request = self.context["request"]
        user = request.user
        product = data["product"]

        has_purchased = OrderItem.objects.filter(
            order__user=user,
            product=product,
            order__status="delivered",
        ).exists()

        if not has_purchased:
            raise serializers.ValidationError(
                "You can only review products you've purchased and received."
            )

        return data

