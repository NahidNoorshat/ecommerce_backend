from rest_framework import serializers
from .models import ProductAnalytics, UserAnalytics

class ProductAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAnalytics
        fields = ['id', 'product', 'total_sales', 'revenue']

class UserAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAnalytics
        fields = ['id', 'user_id', 'total_orders', 'total_spent']
