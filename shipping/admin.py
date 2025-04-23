from django.contrib import admin
from .models import ShippingAddress, ShippingMethod  # Assuming these models exist

admin.site.register(ShippingAddress)
admin.site.register(ShippingMethod)

