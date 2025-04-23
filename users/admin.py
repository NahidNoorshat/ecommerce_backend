from django.contrib import admin
from django.contrib.auth.hashers import make_password
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'is_staff', 'is_superuser', 'is_verified', 'is_active')
    list_filter = ('role', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email', 'role')
    ordering = ('username',)

    def save_model(self, request, obj, form, change):
        # Ensure password is hashed before saving
        if not obj.password.startswith('pbkdf2_'):
            obj.password = make_password(obj.password)
        super().save_model(request, obj, form, change)
