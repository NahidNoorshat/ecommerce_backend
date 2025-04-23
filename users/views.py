from django.db import IntegrityError
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import CustomUser
from .serializers import UserSerializer

class IsAdminOrStaff(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.role == 'admin' or request.user.is_staff or request.user.is_superuser
        )

class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['username', 'email', 'role']
    ordering_fields = ['date_joined', 'username']
    ordering = ['date_joined']

    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            return [IsAdminOrStaff()]
        return [IsAuthenticated()]
    

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Explicitly pass password to ensure it's handled by serializer.create()
        user = serializer.save(password=request.data.get("password"))

        return Response(self.get_serializer(user).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """ Handle user updates securely, allowing only profile updates for non-admins. """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        # Allow superuser, staff, or admin role to update any user
        if not request.user.is_staff and not request.user.is_superuser and not request.user.role == "admin" and request.user != instance:
            return Response({"error": "You can only update your own profile."}, status=status.HTTP_403_FORBIDDEN)

        # Restrict normal users to updating only profile_picture and name
        allowed_fields = ["profile_picture", "first_name", "last_name", "phone_number", "address"]

        if not request.user.is_staff and not request.user.is_superuser and request.user.role != "admin":
            for field in request.data.keys():
                if field not in allowed_fields:
                    return Response({"error": f"You cannot update '{field}' field."}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            self.perform_update(serializer)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except IntegrityError:
            return Response({"error": "Username already exists. Please choose a different one."}, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=True, methods=['patch'], permission_classes=[IsAdminOrStaff])
    def toggle_active(self, request, pk=None):
        user = self.get_object()
        
        if request.user == user:
            return Response({"error": "You cannot deactivate your own account."}, status=status.HTTP_403_FORBIDDEN)

        user.is_active = not user.is_active
        user.save()
        status_text = "activated" if user.is_active else "deactivated"
        return Response({"status": f"User has been {status_text}."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminOrStaff])
    def verify(self, request, pk=None):
        user = self.get_object()
        if user.is_verified:
            return Response({'status': 'User is already verified.'}, status=status.HTTP_400_BAD_REQUEST)
        
        user.is_verified = True
        user.save()
        return Response({'status': 'User verified'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminOrStaff])
    def change_role(self, request, pk=None):
        user = self.get_object()
        new_role = request.data.get("role")

        valid_roles = ["customer", "seller", "admin"]
        if new_role not in valid_roles:
            return Response({"error": "Invalid role"}, status=status.HTTP_400_BAD_REQUEST)

        if user.is_superuser and not request.user.is_superuser:
            return Response({"error": "You cannot change the role of a superuser."}, status=status.HTTP_403_FORBIDDEN)

        user.role = new_role
        user.save()
        return Response({"status": f"User role changed to {new_role}."}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


    @action(detail=True, methods=["post"], url_path="request-seller", permission_classes=[IsAuthenticated])
    def request_seller(self, request, pk=None):
        if str(request.user.id) != pk and not request.user.is_staff:
            return Response({"error": "You can only request for your own account."}, status=403)

        reason = request.data.get("reason", "")
        business_name = request.data.get("business_name", "")
        phone = request.data.get("phone", "")
        website = request.data.get("website", "")

        if not reason:
            return Response({"error": "Reason is required."}, status=400)

        user = self.get_object()
        user.is_seller_requested = True
        user.save()

        return Response(
            {"status": "Your request has been submitted and will be reviewed by an admin."},
            status=200,
        )
    
    @action(detail=True, methods=['patch'], permission_classes=[IsAdminOrStaff])
    def approve_seller(self, request, pk=None):
        user = self.get_object()

        if not user.is_seller_requested:
            return Response({"error": "This user has not requested seller access."}, status=400)

        user.role = "seller"
        user.is_seller_requested = False
        user.save()
        return Response({"status": f"{user.username} is now a seller."})

