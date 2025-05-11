# reviews/models.py

from django.db import models
from django.conf import settings
from products.models import Product  # adjust as needed

class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(default=5)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['product', 'user']  # 1 review per product per user
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} - {self.product} - {self.rating}'
    

