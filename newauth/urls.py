from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView  # Import the refresh token view
from .views import RegisterView, LoginView, ChangePasswordView, UserDetailsView, LogoutView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('user/', UserDetailsView.as_view(), name='user-details'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),  # Add this line
]