import logging
from django.utils import timezone
from django.db.models import Q, Count
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import ChatRoom, Message
from .serializers import ChatRoomSerializer, MessageSerializer, ChatCreateSerializer
from rest_framework.exceptions import ValidationError 

logger = logging.getLogger(__name__)

class ChatRoomListView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        return ChatCreateSerializer if self.request.method == 'POST' else ChatRoomSerializer

    def get_queryset(self):
        if self.request.user.is_staff or getattr(self.request.user, 'role', None) == 'admin':
            # Admins see all active chat rooms
            queryset = ChatRoom.objects.filter(is_active=True)
        else:
            # Non-admins see only their own rooms
            queryset = ChatRoom.objects.filter(
                Q(customer=self.request.user) | Q(assigned_to=self.request.user),
                is_active=True
            )
        
        queryset = queryset.select_related('customer', 'assigned_to', 'product').annotate(
            unread_messages_count=Count(
                'messages',
                filter=Q(messages__is_read=False) & ~Q(messages__sender=self.request.user)
            )
        )
        
        logger.debug(f"User {self.request.user} accessed {queryset.count()} chat rooms")
        return queryset

    def perform_create(self, serializer):
        try:
            serializer.save(customer=self.request.user)
            logger.info(f"New chat room created: {serializer.instance.id}")
        except Exception as e:
            logger.error(f"Chat creation failed: {str(e)}", exc_info=True)
            raise ValidationError(str(e))

class ChatRoomDetailView(generics.RetrieveAPIView):
    serializer_class = ChatRoomSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_staff or getattr(self.request.user, 'role', None) == 'admin':
            # Admins can access any chat room
            return ChatRoom.objects.all()
        # Non-admins can only access their own rooms
        return ChatRoom.objects.filter(
            Q(customer=self.request.user) | Q(assigned_to=self.request.user)
        ).select_related('customer', 'assigned_to', 'product').annotate(
            unread_messages_count=Count(
                'messages',
                filter=Q(messages__is_read=False) & ~Q(messages__sender=self.request.user)
            )
        )
class MessageListView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        room_id = self.kwargs['room_id']
        
        if self.request.user.is_staff or getattr(self.request.user, 'role', None) == 'admin':
            # Admins can access messages in any room
            if not ChatRoom.objects.filter(id=room_id).exists():
                logger.warning(f"Room {room_id} not found for admin {self.request.user}")
                return Message.objects.none()
        else:
            # Non-admins can only access their own rooms
            if not ChatRoom.objects.filter(
                Q(id=room_id) & 
                (Q(customer=self.request.user) | Q(assigned_to=self.request.user))
            ).exists():
                logger.warning(f"Unauthorized access attempt to room {room_id} by user {self.request.user}")
                return Message.objects.none()
        
        return Message.objects.filter(
            room_id=room_id
        ).select_related('sender', 'room').order_by('timestamp')

    def perform_create(self, serializer):
        room_id = self.kwargs['room_id']
        try:
            if self.request.user.is_staff or getattr(self.request.user, 'role', None) == 'admin':
                # Admins can post in any room
                room = ChatRoom.objects.get(id=room_id)
            else:
                # Non-admins can only post in their own rooms
                room = ChatRoom.objects.select_related('customer', 'assigned_to').get(
                    Q(id=room_id) & 
                    (Q(customer=self.request.user) | Q(assigned_to=self.request.user))
                )
            
            message = serializer.save(
                sender=self.request.user,
                room=room
            )
            
            # Auto-mark as read if admin replies
            if self.request.user.is_staff or getattr(self.request.user, 'role', None) == 'admin':
                message.mark_as_read()
            
            # Update room's last message
            room.last_message = timezone.now()
            room.save()
            
            logger.info(f"New message {message.id} created in room {room_id}")
            
        except ChatRoom.DoesNotExist:
            logger.error(f"Chat room access denied for user {self.request.user}")
            raise ValidationError({
                "detail": "You don't have permission to post in this chat",
                "code": "no_chat_permission"
            })

class MarkMessagesReadView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        room_id = kwargs['room_id']
        try:
            if request.user.is_staff or getattr(request.user, 'role', None) == 'admin':
                # Admins can mark messages in any room
                room = ChatRoom.objects.get(id=room_id)
            else:
                # Non-admins can only mark messages in their own rooms
                room = ChatRoom.objects.get(
                    Q(id=room_id) & 
                    (Q(customer=request.user) | Q(assigned_to=request.user))
                )
            
            updated = Message.objects.filter(
                room=room,
                is_read=False
            ).exclude(
                sender=request.user
            ).update(
                is_read=True,
                read_timestamp=timezone.now()
            )
            
            logger.info(f"User {request.user} marked {updated} messages as read in room {room_id}")
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except ChatRoom.DoesNotExist:
            logger.warning(f"Invalid room access attempt: user {request.user}, room {room_id}")
            return Response(
                {
                    "detail": "Chat room not found or access denied",
                    "code": "invalid_room"
                },
                status=status.HTTP_403_FORBIDDEN
            )