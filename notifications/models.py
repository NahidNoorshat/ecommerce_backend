from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    notification_type = models.CharField(max_length=50, default='general')  # e.g., 'order', 'promo', 'review'

    # ✅ Add flexible JSON field to hold anything like product_slug, etc.
    data = models.JSONField(blank=True, null=True, default=dict)

    def __str__(self):
        return f"To: {self.user.email} | {self.title}"
