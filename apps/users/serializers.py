from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.users.models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "password", "password_confirm", "first_name", "last_name", "role"]
        extra_kwargs = {
            "role": {"default": User.Role.DATA_VIEWER},
        }

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role", "created_at", "updated_at"]
        read_only_fields = ["id", "email", "role", "created_at", "updated_at"]


class UserManagementSerializer(serializers.ModelSerializer):
    """Admin-only serializer for full user management."""

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "role",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "email", "created_at", "updated_at"]
