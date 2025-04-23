from rest_framework import serializers
from .models import ShippingAddress, ShippingMethod

class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = [
            'id', 'user', 'order', 'address_line_1', 'address_line_2', 
            'city', 'state', 'postal_code', 'country', 'phone'
        ]

class ShippingMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingMethod
        fields = ['id', 'name', 'description', 'price']
