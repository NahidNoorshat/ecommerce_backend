from django.db import models
from django.conf import settings
from django.db.models import Q, Count
from products.models import Product
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError

User = get_user_model()

class ChatRoom(models.Model):
    class ChatType(models.TextChoices):
        PRODUCT = 'product', 'Product Inquiry'
        SUPPORT = 'support', 'General Support'
        ORDER = 'order', 'Order Related'

    chat_type = models.CharField(
        max_length=20,
        choices=ChatType.choices,
        default=ChatType.PRODUCT
    )
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='chat_rooms'
    )
    
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='customer_chats'
    )
    
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_chats'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_message = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_resolved = models.BooleanField(default=False)

    class Meta:
        constraints = [
            # Ensures only one active product chat per customer-product pair
            models.UniqueConstraint(
                fields=['product', 'customer'],
                name='unique_active_product_chat',
                condition=Q(is_active=True, chat_type='product')
            ),
            # General unique constraint for all active chats
            models.UniqueConstraint(
                fields=['product', 'customer', 'is_active'],
                name='unique_user_product_chat',
                condition=Q(is_active=True)
            )
        ]
        indexes = [
            models.Index(fields=['assigned_to', 'is_active']),
            models.Index(fields=['last_message']),
            models.Index(fields=['product', 'customer', 'is_active']),
        ]

    def clean(self):
        """Validation rules"""
        if self.is_active and self.assigned_to == self.customer:
            raise ValidationError("Customer cannot be assigned to their own chat")
        
        if self.chat_type == self.ChatType.PRODUCT and not self.product:
            raise ValidationError("Product chat must have a product")

    def save(self, *args, **kwargs):
        """Auto-assigns admin if not specified"""
        self.full_clean()  # Runs clean() validation
        
        if self.chat_type == self.ChatType.PRODUCT and not self.assigned_to:
            self.assigned_to = User.objects.filter(
                Q(is_staff=True) | Q(role='admin')
            ).first()
            
        super().save(*args, **kwargs)

    @property
    def websocket_group_name(self):
        """Standardized WebSocket group name"""
        return f"chat_{self.chat_type}_{self.product_id if self.product else 'support'}_user_{self.customer_id}"

    @property
    def unread_message_count(self):
        return self.messages.filter(is_read=False).exclude(sender=self.customer).count()

    def __str__(self):
        base = f"{self.get_chat_type_display()} Chat #{self.id}"
        return f"{base} - {self.product.name[:20]}" if self.product else base

class Message(models.Model):
    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    read_timestamp = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['room', 'is_read']),
            models.Index(fields=['sender', 'timestamp']),
            models.Index(fields=['room', 'sender', 'is_read']),
        ]
        get_latest_by = 'timestamp'

    def clean(self):
        """Validate sender is a chat participant, unless they are an admin"""
        if not (self.sender.is_staff or getattr(self.sender, 'role', None) == 'admin'):
            if self.sender not in [self.room.customer, self.room.assigned_to]:
                raise ValidationError("Sender must be a chat participant")

    def save(self, *args, **kwargs):
        self.full_clean()

        is_new = not self.pk

        # Ensure `is_read` is set correctly based on sender
        if is_new and not self.is_read:
            if self.sender == self.room.customer:
                self.is_read = False  # sent by customer → admin has not read yet
            else:
                self.is_read = True  # sent by admin → customer can see immediately

        super().save(*args, **kwargs)

        # Update room last message timestamp AFTER message saved
        if is_new:
            self.room.last_message = self.timestamp
            self.room.save(update_fields=["last_message"])


    def mark_as_read(self):
        """Mark message as read with timestamp"""
        if not self.is_read:
            self.is_read = True
            self.read_timestamp = timezone.now()
            self.save()
            return True
        return False
    
    def mark_all_messages_as_read_by_customer(self):
        self.messages.filter(
            is_read=False,
            sender=self.customer
        ).update(is_read=True, read_timestamp=timezone.now())


    def __str__(self):
        return f"{self.sender.username} ({self.timestamp:%Y-%m-%d %H:%M}): {self.content[:30]}"