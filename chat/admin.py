from django.contrib import admin
from .models import ChatRoom, Message

@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat_type', 'product', 'customer', 'assigned_to', 'is_active')
    list_filter = ('chat_type', 'is_active')
    search_fields = ('customer__username', 'assigned_to__username', 'product__name')
    raw_id_fields = ('product', 'customer', 'assigned_to')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'room', 'sender', 'timestamp', 'is_read')
    list_filter = ('is_read', 'timestamp')
    search_fields = ('sender__username', 'content')
    raw_id_fields = ('room', 'sender')