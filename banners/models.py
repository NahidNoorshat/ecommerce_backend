# banners/models.py

from django.db import models
from orders.models import Coupon  # Adjust the import according to your project

class Banner(models.Model):
    title = models.CharField(max_length=255)
    subtitle = models.TextField(blank=True, null=True)
    discount_text = models.CharField(max_length=50, blank=True, null=True)
    coupon = models.ForeignKey(Coupon, blank=True, null=True, on_delete=models.SET_NULL)
    image = models.ImageField(upload_to="banners/")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.title
