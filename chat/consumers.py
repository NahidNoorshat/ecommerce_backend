import json
import logging
from urllib.parse import parse_qs
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.utils import timezone
from django.db.models import Q, Count, F
from .models import ChatRoom, Message, Product
from .serializers import ChatRoomSerializer, MessageSerializer
from asgiref.sync import sync_to_async
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request


logger = logging.getLogger(__name__)
User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            # Authentication
            query_params = parse_qs(self.scope['query_string'].decode())
            token = query_params.get('token', [None])[0]
            
            if not token:
                logger.warning("No token provided in WebSocket connection")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Authentication token is required'
                }))
                await self.close(code=4001)
                return

            jwt_auth = JWTAuthentication()
            try:
                validated_token = await database_sync_to_async(jwt_auth.get_validated_token)(token)
            except (InvalidToken, TokenError) as e:
                logger.warning(f"Invalid token: {str(e)}")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Invalid or expired token'
                }))
                await self.close(code=4001)
                return

            user = await database_sync_to_async(jwt_auth.get_user)(validated_token)
            if not user.is_authenticated:
                logger.warning(f"User not authenticated for token: {token}")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'User authentication failed'
                }))
                await self.close(code=4001)
                return

            self.user = user
            self.scope['user'] = user

            # Extract room parameters
            room_name = self.scope['url_route']['kwargs']['room_name']
            try:
                _, product_id, _, user_id = room_name.split('_')
                product_id = int(product_id)
                user_id = int(user_id)
            except (ValueError, AttributeError):
                logger.warning(f"Invalid room name format: {room_name}")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Invalid room name format'
                }))
                await self.close(code=4003)
                return

            # Validate user access
            if user.id != user_id and not (user.is_staff or getattr(user, 'role', None) == "admin"):
                logger.warning(f"User {user.username} not authorized for room {room_name}")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'You are not authorized to access this chat'
                }))
                await self.close(code=4003)
                return

            # Get or create chat room
            product = await self.get_product(product_id)
            if not product:
                logger.warning(f"Product {product_id} not found")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Product not found'
                }))
                await self.close(code=4004)
                return

            self.room = await self.get_or_create_chat_room(product_id, user_id)

            if not self.room:
                logger.error(f"Failed to get or create chat room for product {product_id} and user {user.id}")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Unable to initialize chat room'
                }))
                await self.close(code=4005)
                return

            self.room_group_name = await database_sync_to_async(lambda: self.room.websocket_group_name)()

            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )

            await self.accept()
            
            # Send connection confirmation
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'Chat connection successful',
                'room_id': self.room.id,
                'user_id': user.id,
                'is_admin': user.is_staff
            }))

            # Send message history
            await self.send_message_history()

        except Exception as e:
            logger.error(f"Connection error: {str(e)}", exc_info=True)
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'An unexpected error occurred during connection'
            }))
            await self.close(code=4001)

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            logger.info(f"Received message data: {data}")
            
            if data.get('type') == 'ping':
                await self.send(json.dumps({'type': 'pong'}))
                return
                
            if data.get('type') in ['chat.message', 'chat_message']:
                if not await self.is_participant():
                    logger.warning(f"User {self.user.username} not a participant in room {self.room.id}")
                    await self.send(json.dumps({
                        'type': 'error',
                        'message': 'You are not a participant in this chat'
                    }))
                    await self.close(code=4003)
                    return

                content = data.get('content', '').strip()
                if not content:
                    await self.send(json.dumps({
                        'type': 'error',
                        'message': 'Message cannot be empty'
                    }))
                    return

                message = await self.create_message(content)
                await self.broadcast_message(message)

            elif data.get('type') == 'mark_read':
                await self.mark_messages_read(data.get('message_ids', []))

        except json.JSONDecodeError:
            await self.send(json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Message processing error: {str(e)}", exc_info=True)
            await self.close(code=4000)

    async def chat_message(self, event):
        """Handler for chat.message events"""
        await self.send(text_data=json.dumps({
            'type': 'chat.message',
            'message': event['message']
        }))

    async def broadcast_message(self, message):
        group_name = await database_sync_to_async(lambda: self.room.websocket_group_name)()

        message_payload = {
            'id': message.id,
            'sender_id': message.sender.id,
            'sender_name': message.sender.username,
            'content': message.content,
            'timestamp': message.timestamp.isoformat(),
            'is_read': message.is_read,
            'is_admin': message.sender.is_staff,
        }

        # 1. Send message to room participants
        await self.channel_layer.group_send(
            group_name,
            {
                'type': 'chat.message',
                'message': message_payload
            }
        )

        # 2. Update unread count if the sender is customer
        if self.user == self.room.customer:
            unread_count = await self.get_unread_count()
            last_message_data = MessageSerializer(message).data
            
            # 3. Notify admin dashboard (admin_notifications group)
            await self.channel_layer.group_send(
                'admin_notifications',
                {
                    'type': 'chat_unread_update',
                    'message': {
                        'room_id': self.room.id,
                        'unread_count': unread_count,
                        'last_message': last_message_data 
                    }
                }
            )


    async def send_message_history(self):
        messages = await self.get_room_messages()
        await self.send(text_data=json.dumps({
            'type': 'message_history',
            'messages': messages
        }))

    @database_sync_to_async
    def get_product(self, product_id):
        try:
            return Product.objects.get(id=product_id)
        except ObjectDoesNotExist:
            return None

    @database_sync_to_async
    def get_unread_count(self):
        return Message.objects.filter(
            room=self.room,
            is_read=False,
            sender=self.room.customer
        ).count()


    @database_sync_to_async
    def get_or_create_chat_room(self, product_id, user_id):
        try:
            product = Product.objects.get(id=product_id)
            customer_user = User.objects.get(id=user_id)

            # Check for existing room
            room = ChatRoom.objects.filter(
                product=product,
                customer=customer_user,
                is_active=True
            ).first()
            if room:
                return room

            # Determine admin user
            if self.user.is_staff or getattr(self.user, 'role', '') == 'admin':
                # Admin is connecting
                admin_user = self.user
            else:
                admin_user = User.objects.filter(
                    Q(is_staff=True) | Q(role='admin')
                ).exclude(id=self.user.id).first()
                if not admin_user:
                    logger.error("No admin available")
                    return None

            # Determine customer
            if self.user == admin_user:
                customer = customer_user
            else:
                customer = self.user

            # Create room
            return ChatRoom.objects.create(
                product=product,
                customer=customer,
                assigned_to=admin_user,
                chat_type='product',
                is_active=True
            )

        except Exception as e:
            logger.error(f"Error creating chat room: {str(e)}", exc_info=True)
            return None


    @database_sync_to_async
    def create_message(self, content):
        message = Message.objects.create(
            room=self.room,
            sender=self.user,
            content=content
        )
        # Auto-mark as read if admin replies
        if self.user == self.room.assigned_to:
            message.mark_as_read()
        return message

    @database_sync_to_async
    def get_room_messages(self):
        messages = Message.objects.filter(
            room=self.room
        ).select_related('sender').order_by('timestamp')[:50]
        return [{
            'id': msg.id,
            'sender_id': msg.sender.id,
            'sender_name': msg.sender.username,
            'content': msg.content,
            'timestamp': msg.timestamp.isoformat(),
            'is_read': msg.is_read,
            'is_admin': msg.sender.is_staff,
        } for msg in messages]

    @database_sync_to_async
    def is_participant(self):
        return self.user in [self.room.customer, self.room.assigned_to]

    @database_sync_to_async
    def mark_messages_read(self, message_ids):
        Message.objects.filter(
            id__in=message_ids,
            room=self.room,
            is_read=False
        ).exclude(
            sender=self.user
        ).update(is_read=True, read_timestamp=timezone.now())

class AdminChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            query_params = parse_qs(self.scope['query_string'].decode())
            token = query_params.get('token', [None])[0]
            
            if not token:
                logger.warning("No token provided in WebSocket connection")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Authentication token is required'
                }))
                await self.close(code=4001)
                return

            jwt_auth = JWTAuthentication()
            try:
                validated_token = await database_sync_to_async(jwt_auth.get_validated_token)(token)
            except (InvalidToken, TokenError) as e:
                logger.warning(f"Invalid token: {str(e)}")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Invalid or expired token'
                }))
                await self.close(code=4001)
                return

            user = await database_sync_to_async(jwt_auth.get_user)(validated_token)
            if not user.is_authenticated:
                logger.warning(f"User not authenticated for token: {token}")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'User authentication failed'
                }))
                await self.close(code=4001)
                return

            if not (user.is_staff or getattr(user, 'role', None) == "admin"):
                logger.warning(f"User {user.username} lacks admin privileges")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'You must be an administrator to access this page'
                }))
                await self.close(code=4001)
                return

            self.user = user
            await self.channel_layer.group_add('admin_notifications', self.channel_name)
            await self.accept()
            
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'Admin chat connection successful',
                'user_id': user.id,
                'is_admin': user.is_staff or getattr(user, 'role', None) == 'admin'
            }))
            
            await self.send_active_chats()

        except Exception as e:
            logger.error(f"Admin connection error: {str(e)}", exc_info=True)
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'An unexpected error occurred during connection'
            }))
            await self.close(code=4001)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard('admin_notifications', self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            
            if data.get('type') == 'ping':
                await self.send(json.dumps({'type': 'pong'}))
                return
                
            elif data.get('type') == 'join_chat':
                await self.join_chat_room(data.get('room_id'))
                    
            elif data.get('type') in ['chat.message', 'chat_message']:
                await self.handle_chat_message(
                    data.get('room_id'),
                    data.get('content', '').strip()
                )
            elif data.get('type') == 'leave_chat':
                await self.leave_chat_room(data.get('room_id'))


        except Exception as e:
            logger.error(f"Admin receive error: {str(e)}", exc_info=True)
            await self.close(code=4000)

    async def handle_chat_message(self, room_id, content):
        """Handle both message formats"""
        if not content:
            await self.send(json.dumps({
                'type': 'error',
                'message': 'Message cannot be empty'
            }))
            return

        room = await self.get_chat_room(room_id)
        if not room:
            await self.send(json.dumps({
                'type': 'error',
                'message': 'Chat room not found'
            }))
            return

        logger.info(f"Admin {self.user.username} sending message to room {room_id}: {content}")
        message = await self.create_message(room, content)
        group_name = await database_sync_to_async(lambda: room.websocket_group_name)()
        
        # Broadcast message to room
        await self.channel_layer.group_send(
            group_name,
            {
                'type': 'chat_message',
                'message': {
                    'id': message.id,
                    'sender_id': self.user.id,
                    'sender_name': self.user.username,
                    'content': content,
                    'timestamp': message.timestamp.isoformat(),
                    'is_read': True,
                    'is_admin': True,
                }
            }
        )

        # Notify other admins
        await self.channel_layer.group_send(
            'admin_notifications',
            {
                'type': 'admin_notification',
                'message': {
                    'event': 'message_sent',
                    'room_id': room.id,
                    'admin_id': self.user.id,
                    'admin_name': self.user.username,
                    'content': content,
                    'timestamp': timezone.now().isoformat()
                }
            }
        )

    async def chat_message(self, event):
        """Handle incoming broadcasted messages from channel layer"""
        await self.send(text_data=json.dumps({
            'type': 'chat.message',
            'message': event['message']
        }))

    async def admin_notification(self, event):
        """Handle admin notifications"""
        await self.send(json.dumps({
            'type': 'admin_notification',
            'message': event['message']
        }))

    async def new_chat_message(self, event):
        await self.send(json.dumps({
            'type': 'new_chat_notification',
            'message': {
                'id': event['message_id'],
                'room_id': event['room_id'],
                'product_id': event['product_id'],
                'customer_id': event['customer_id'],
                'customer_name': event['customer_name'],
                'content': event['content'],
                'timestamp': event['timestamp']
            }
        }))

    async def send_active_chats(self):
        chats = await self.get_active_chats()
        await self.send(json.dumps({
            'type': 'active_chats',
            'chats': chats
        }, default=str))

    async def join_chat_room(self, room_id):
        room = await self.get_chat_room(room_id)
        if not room:
            await self.send(json.dumps({
                'type': 'error',
                'message': 'Chat room not found'
            }))
            return

        logger.info(f"Admin {self.user.username} (ID: {self.user.id}) joined room {room.id}")
        group_name = await database_sync_to_async(lambda: room.websocket_group_name)()
        await self.channel_layer.group_add(group_name, self.channel_name)

        await self.mark_customer_messages_as_read(room.id)

        # ✅ Notify other dashboards
        await self.channel_layer.group_send(
            'admin_notifications',
            {
                'type': 'chat_unread_update',
                'message': {
                    'room_id': room.id,
                    'unread_count': 0
                }
            }
        )

        await self.channel_layer.group_send(
            'admin_notifications',
            {
                'type': 'admin_notification',
                'message': {
                    'event': 'admin_joined',
                    'room_id': room.id,
                    'admin_id': self.user.id,
                    'admin_name': self.user.username,
                    'timestamp': timezone.now().isoformat()
                }
            }
        )

        # ✅ FIXED: async-safe serialization
        serialized_room = await serialize_chat_room(room, self.scope)


        await self.send(json.dumps({
            'type': 'chat_room_joined',
            'room': serialized_room,
            'messages': await self.get_room_messages(room)
        }, cls=DjangoJSONEncoder))


    async def send_chat_message(self, room_id, content):
        if not content:
            await self.send(json.dumps({
                'type': 'error',
                'message': 'Message cannot be empty'
            }))
            return

        room = await self.get_chat_room(room_id)
        if not room:
            await self.send(json.dumps({
                'type': 'error',
                'message': 'Chat room not found'
            }))
            return

        message = await self.create_message(room, content)
        group_name = await database_sync_to_async(lambda: room.websocket_group_name)()
        
        await self.channel_layer.group_send(
            group_name,
            {
                'type': 'chat_message',
                'message': {
                    'id': message.id,
                    'sender_id': self.user.id,
                    'sender_name': self.user.username,
                    'content': content,
                    'timestamp': message.timestamp.isoformat(),
                    'is_read': True,
                    'is_admin': True,
                }
            }
        )


    async def chat_unread_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat_unread_update',
            'message': event['message']
        }))

    
    async def leave_chat_room(self, room_id):
        room = await self.get_chat_room(room_id)
        if not room:
            await self.send(json.dumps({
                'type': 'error',
                'message': 'Chat room not found'
            }))
            return

        group_name = await database_sync_to_async(lambda: room.websocket_group_name)()
        await self.channel_layer.group_discard(group_name, self.channel_name)

        logger.info(f"Admin {self.user.username} left room {room.id}")

        await self.send(json.dumps({
            'type': 'chat_room_left',
            'room_id': room.id
        }))


    
    @database_sync_to_async
    def get_active_chats(self):
        from rest_framework.test import APIRequestFactory
        from rest_framework.request import Request

        chats = ChatRoom.objects.filter(
            is_active=True
        ).select_related(
            'product', 'customer', 'assigned_to'
        ).prefetch_related(
            'messages'
        ).annotate(
            unread_count=Count(
                'messages',
                filter=Q(messages__is_read=False) & Q(messages__sender=F('customer'))
            )
        ).order_by('-last_message')[:50]

        # ✅ Extract host dynamically from WebSocket headers
        headers = dict(self.scope.get("headers", []))
        host = headers.get(b"host", b"127.0.0.1:8000").decode()

        # ❌ Don't try to manually set scheme
        factory = APIRequestFactory()
        request = factory.get("/", HTTP_HOST=host)

        serializer = ChatRoomSerializer(chats, many=True, context={'request': Request(request)})
        return serializer.data






    @database_sync_to_async
    def get_chat_room(self, room_id):
        try:
            return ChatRoom.objects.select_related('product', 'customer').get(id=room_id)
        except (ObjectDoesNotExist, ValueError):
            return None

    @database_sync_to_async
    def create_message(self, room, content):
        logger.info(f"Creating message for room {room.id} by admin {self.user.username}")
        message = Message.objects.create(
            room=room,
            sender=self.user,
            content=content,
            is_read=True  # Admin messages are auto-read
        )
        return message

    @database_sync_to_async
    def get_room_messages(self, room):
        messages = Message.objects.filter(room=room).select_related('sender').order_by('timestamp')[:100]
        return [{
            'id': msg.id,
            'sender_id': msg.sender.id,
            'sender_name': msg.sender.username,
            'content': msg.content,
            'timestamp': msg.timestamp.isoformat(),
            'is_read': msg.is_read,
            'is_admin': msg.sender.is_staff,
        } for msg in messages]
    
    @database_sync_to_async
    def mark_customer_messages_as_read(self, chat_room_id):
        from django.utils import timezone
        from chat.models import ChatRoom

        room = ChatRoom.objects.filter(id=chat_room_id).first()
        if room:
            room.messages.filter(
                is_read=False,
                sender=room.customer  # ✅ This is a resolved user instance
            ).update(is_read=True, read_timestamp=timezone.now())

@database_sync_to_async
def serialize_chat_room(room, scope):
    from rest_framework.test import APIRequestFactory
    from rest_framework.request import Request
    from .serializers import ChatRoomSerializer

    headers = dict(scope.get("headers", []))
    host = headers.get(b"host", b"127.0.0.1:8000").decode()
    scheme = "https" if scope.get("scheme") == "https" else "http"

    factory = APIRequestFactory()
    request = factory.get("/", HTTP_HOST=host)
    

    return ChatRoomSerializer(room, context={'request': Request(request)}).data

