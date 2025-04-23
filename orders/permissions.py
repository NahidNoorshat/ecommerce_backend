from rest_framework.permissions import BasePermission

class IsAdminOrStaff(BasePermission):
    """
    Allow access if user is staff or has role='admin'
    """
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and (
                request.user.is_staff or request.user.role == 'admin'
            )
        )
