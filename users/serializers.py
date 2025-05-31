from rest_framework import serializers
from .models import CustomUser

class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=False)
    username = serializers.CharField(min_length=3, max_length=150, required=False)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'role', 'password',
            'profile_picture', 'phone_number', 'address', 'is_verified', 'is_active'
        ]
        extra_kwargs = {
            'id': {'read_only': True},
            'username': {'required': False},
        }

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = CustomUser(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

    def validate_email(self, value):
        if self.instance:
            if value != self.instance.email and CustomUser.objects.exclude(id=self.instance.id).filter(email=value).exists():
                raise serializers.ValidationError("This email is already in use.")
        else:
            if CustomUser.objects.filter(email=value).exists():
                raise serializers.ValidationError("This email is already in use.")
        return value

    def validate_phone_number(self, value):
        if value and not value.isdigit():
            raise serializers.ValidationError("Phone number must contain only digits.")
        return value


class UserBasicSerializer(serializers.ModelSerializer):
    """
    Lightweight user serializer for chat system and other basic listings
    Includes only essential fields to reduce payload size
    """
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            'id',
            'username',
            'first_name',
            'last_name',
            'role',
            'profile_picture_url'
        ]
        read_only_fields = fields

    def get_profile_picture_url(self, obj):
        """Generate full URL for profile picture if exists"""
        request = self.context.get('request')
        if obj.profile_picture:
            if request:
                return request.build_absolute_uri(obj.profile_picture.url)
            return obj.profile_picture.url
        return None