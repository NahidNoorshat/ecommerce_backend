from django.contrib import admin
from .models import Notification

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'is_read', 'notification_type', 'created_at')
    list_filter = ('is_read', 'notification_type')
    search_fields = ('title', 'user__email')
