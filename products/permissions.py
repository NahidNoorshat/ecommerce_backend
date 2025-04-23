from rest_framework import permissions

class IsCustomerOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        # Check if user is authenticated and has 'customer' role
        if not request.user.is_authenticated:
            return False
        if hasattr(request.user, 'role'):
            is_customer = request.user.role == 'customer'
            if not is_customer:
                self.message = "Only customers can manage cart items."
            return is_customer
        return False  # Default to False if no role (assuming customer is explicit)

    def has_object_permission(self, request, view, obj):
        # For update/delete, ensure the item belongs to the customer
        return obj.user == request.user and request.user.role == 'customer'