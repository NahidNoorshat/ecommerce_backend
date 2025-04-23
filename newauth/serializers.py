from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from users.models import CustomUser

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        error_messages={
            'blank': 'Password cannot be blank.',
            'required': 'Password is required.',
        }
    )
    confirm_password = serializers.CharField(
        write_only=True,
        error_messages={
            'blank': 'Confirm password cannot be blank.',
            'required': 'Confirm password is required.',
        }
    )

    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'password', 'confirm_password', 'role',
            'profile_picture', 'phone_number', 'address'  # Add new fields here
        ]

    def validate(self, data):
        # Check if passwords match
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        
        # Validate password complexity
        try:
            validate_password(data['password'])
        except ValidationError as e:
            raise serializers.ValidationError({"password": e.messages})
        
        return data

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_username(self, value):
        if CustomUser.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_role(self, value):
        if value not in ["customer"]:
            raise serializers.ValidationError("Only customers can register directly. Admin or seller must be created by an admin.")
        return value

    def create(self, validated_data):
        # Remove confirm_password from validated_data
        validated_data.pop('confirm_password')
        # Force role to be customer
        validated_data['role'] = 'customer'

        # Use create_user for proper password hashing
        user = CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            role=validated_data.get('role', 'customer'),  # Default role if not provided
            profile_picture=validated_data.get('profile_picture'),  # Add new fields here
            phone_number=validated_data.get('phone_number'),
            address=validated_data.get('address'),
        )
        return user