from django.contrib import admin
from .models import ProductAnalytics, UserAnalytics  # Assuming these models exist

admin.site.register(ProductAnalytics)
admin.site.register(UserAnalytics)

