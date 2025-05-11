# orders/models.py
import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from products.models import Product, ProductVariant

import logging

logger = logging.getLogger(__name__)

class Coupon(models.Model):
    code = models.CharField(max_length=20, unique=True)
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Discount percentage (0-100)"
    )
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="Max number of uses, null for unlimited")
    uses = models.PositiveIntegerField(default=0, help_text="Number of times used")

    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        return (
            self.is_active and
            self.valid_from <= now <= self.valid_until and
            (self.max_uses is None or self.uses < self.max_uses)
        )

    def __str__(self):
        return f"{self.code} - {self.discount_percentage}% off"

class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )
    
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ('cod', 'Cash on Delivery'),
        ('card', 'Credit/Debit Card'),
        ('paypal', 'PayPal'),
        ('crypto', 'Cryptocurrency'),
    )

    # State transition rules
    VALID_TRANSITIONS = {
        'pending': ['processing', 'cancelled'],
        'processing': ['shipped', 'cancelled'],
        'shipped': ['delivered'],
        'delivered': [],
        'cancelled': [],
    }

    order_id = models.CharField(
        max_length=36,
        unique=True,
        editable=False,
        default=uuid.uuid4
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, null=True, blank=True)
    payment_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_method = models.ForeignKey(
        'shipping.ShippingMethod',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders'
    )
    
    def calculate_total(self, coupon=None):
        from decimal import Decimal
        items = self.items.all()
        subtotal = sum(
            Decimal(str(item.price_at_purchase)) * Decimal(str(item.quantity))
            for item in items
        )
        shipping_cost = Decimal('0.00')
        if self.shipping_method:
            shipping_cost = Decimal(str(self.shipping_method.price))
            logger.info(f"Applied shipping cost: {shipping_cost} for method {self.shipping_method.name}")
        self.discount_amount = Decimal('0.00')
        if coupon and coupon.is_valid():
            discount = (Decimal(str(coupon.discount_percentage)) / Decimal('100')) * subtotal
            self.discount_amount = discount.quantize(Decimal('0.01'))
            logger.info(f"Applied discount: {self.discount_amount} from coupon {coupon.code}")
        self.total_price = (subtotal + shipping_cost - self.discount_amount).quantize(Decimal('0.01'))
        self.save()
        logger.info(f"Order {self.order_id} total calculated: {self.total_price}, shipping: {shipping_cost}, discount: {self.discount_amount}")
    
    def transition_to(self, new_status):
        if new_status not in self.VALID_TRANSITIONS.get(self.status, []):
            raise ValueError(f"Cannot transition from {self.status} to {new_status}")
        
        self.status = new_status
        # Auto-update payment_status for COD when delivered
        if new_status == 'delivered' and self.payment_method == 'cod':
            self.payment_status = 'paid'
            logger.info(f"Order {self.order_id} delivered with COD, payment marked as paid")
        
        self.save()
        logger.info(f"Order {self.order_id} transitioned to {new_status}")

    def __str__(self):
        return f"Order {self.order_id} - {self.user.username} - {self.status}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} - {self.quantity} pcs"