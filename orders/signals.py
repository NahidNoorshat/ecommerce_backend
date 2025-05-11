from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order
from notifications.models import Notification
from django.contrib.auth import get_user_model
from notifications.utils import create_and_push_notification

User = get_user_model()

@receiver(post_save, sender=Order)
def order_status_notification(sender, instance, created, **kwargs):
    if created:
        # Notify customer
        create_and_push_notification(
            user=instance.user,
            title="Order Placed",
            message=f"Your order #{instance.order_id} has been placed successfully.",
            notification_type="order"
        )

        # Notify admins
        admins = User.objects.filter(role='admin', is_active=True)
        for admin in admins:
            create_and_push_notification(
                user=admin,
                title="New Order Received",
                message=f"Order #{instance.order_id} placed by {instance.user.email}.",
                notification_type="order"
            )

    elif instance.status == "delivered":
        create_and_push_notification(
            user=instance.user,
            title="Order Delivered",
            message=f"Your order #{instance.order_id} has been delivered. Thank you!",
            notification_type="order"
        )

    elif instance.status == "cancelled":
        create_and_push_notification(
            user=instance.user,
            title="Order Cancelled",
            message=f"Your order #{instance.order_id} has been cancelled.",
            notification_type="cancel"
        )

