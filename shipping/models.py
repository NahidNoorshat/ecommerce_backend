from django.db import models
from django.conf import settings
from orders.models import Order

class ShippingAddress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='shipping_address', null=True, blank=True)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    delivered_at = models.DateTimeField(null=True, blank=True)

    def mark_delivered(self):
        from django.utils import timezone
        self.delivered_at = timezone.now()
        self.save()
        self.order.transition_to('delivered')

    def __str__(self):
        return f"Shipping Address for Order {self.order.id} - {self.user.username}"


class ShippingMethod(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name

