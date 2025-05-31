from django.urls import path
from .views import (
    ChatRoomListView,
    ChatRoomDetailView,
    MessageListView,
    MarkMessagesReadView
)

urlpatterns = [
    path('chats/', ChatRoomListView.as_view(), name='chat-list'),
    path('chats/<int:pk>/', ChatRoomDetailView.as_view(), name='chat-detail'),
    path('chats/<int:room_id>/messages/', MessageListView.as_view(), name='message-list'),
    path('chats/<int:room_id>/read/', MarkMessagesReadView.as_view(), name='mark-read'),
]