from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model
from .serializers import RegisterSerializer
from django.contrib.auth import update_session_auth_hash
from users.serializers import UserSerializer
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from users.serializers import UserSerializer
User = get_user_model()

# RegisterView for handling user registration
class RegisterView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User registered successfully"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# LoginView for handling user login and JWT generation
class LoginView(APIView):
    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response({
                "username": ["This field is required."] if not username else [],
                "password": ["This field is required."] if not password else []
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            return Response({"username": ["No user found with this username."]}, status=400)
        except User.MultipleObjectsReturned:
            return Response({"username": ["Multiple accounts found. Please contact support."]}, status=400)

        if not user.check_password(password):
            return Response({"password": ["Incorrect password."]}, status=400)

        if not user.is_active:
            return Response({"username": ["This account is inactive."]}, status=400)

        refresh = RefreshToken.for_user(user)

        # ✅ Use full serializer to include `id` and all user fields
        user_data = UserSerializer(user).data

        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": user_data
        })

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        # Check if the old password is correct
        if not user.check_password(old_password):
            return Response({'error': 'Old password is incorrect'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate the new password
        try:
            validate_password(new_password, user)
        except ValidationError as e:
            return Response({'error': e.messages}, status=status.HTTP_400_BAD_REQUEST)

        # Set the new password
        user.set_password(new_password)
        user.save()

        # Update session authentication hash
        update_session_auth_hash(request, user)

        return Response({'message': 'Password changed successfully'}, status=status.HTTP_200_OK)

class UserDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    @csrf_exempt  # Apply csrf_exempt to the dispatch method
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        user = request.user
        serializer = UserSerializer(user)
        return Response(serializer.data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request): 
        try:
            # Get the refresh token from the request body
            refresh_token = request.data.get('refresh_token')
            if not refresh_token:
                return Response({"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)

            # Blacklist the refresh token (optional)
            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response({"message": "Logged out successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)