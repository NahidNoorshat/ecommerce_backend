from django.db import models
from products.models import Product
from orders.models import Order

class ProductAnalytics(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    total_sales = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.product.name} - Sales: {self.total_sales} - Revenue: ${self.revenue}"

class UserAnalytics(models.Model):
    user_id = models.PositiveIntegerField()
    total_orders = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"User {self.user_id} - Orders: {self.total_orders} - Spent: ${self.total_spent}"
