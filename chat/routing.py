from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<room_name>product_\d+_user_\d+)/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/admin/chat/$', consumers.AdminChatConsumer.as_asgi()),
]