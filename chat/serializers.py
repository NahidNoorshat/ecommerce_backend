from rest_framework import serializers
from .models import ChatRoom, Message
from users.serializers import UserBasicSerializer
from products.serializers import ProductSimpleSerializer

class MessageSerializer(serializers.ModelSerializer):
    sender = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = Message
        fields = ['id', 'sender', 'content', 'timestamp', 'is_read']
        read_only_fields = ['timestamp', 'is_read']


class ChatRoomSerializer(serializers.ModelSerializer):
    product = ProductSimpleSerializer(read_only=True)
    customer = UserBasicSerializer(read_only=True)
    assigned_to = UserBasicSerializer(read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    recent_messages = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = [
            'id', 'chat_type', 'product', 'customer', 'assigned_to',
            'is_active', 'unread_count', 'last_message', 'recent_messages'
        ]

    def get_last_message(self, obj):
        last_msg = obj.messages.order_by('-timestamp').first()
        return MessageSerializer(last_msg).data if last_msg else None

    def get_recent_messages(self, obj):
        messages = obj.messages.order_by('-timestamp')[:10]
        return MessageSerializer(reversed(messages), many=True).data

    def get_unread_count(self, obj):
        return obj.messages.filter(is_read=False, sender__role='customer').count()



    


class ChatCreateSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(required=False)

    class Meta:
        model = ChatRoom
        fields = ['chat_type', 'product_id']
        extra_kwargs = {
            'chat_type': {'required': True}
        }

    def validate(self, data):
        if data['chat_type'] == ChatRoom.ChatType.PRODUCT and not data.get('product_id'):
            raise serializers.ValidationError("Product ID required for product chats")
        return data