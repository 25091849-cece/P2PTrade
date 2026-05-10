"""
REST API Serializers for authentication and user accounts.
"""

from rest_framework import serializers
from accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'name', 'role', 'is_active', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')


class UserDetailSerializer(UserSerializer):
    """Detailed serializer for User model with additional fields."""

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ('failed_login_attempts', 'locked_until', 'is_account_locked')
        read_only_fields = UserSerializer.Meta.read_only_fields + ('failed_login_attempts', 'locked_until')


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    password = serializers.CharField(write_only=True, min_length=6)
    password2 = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ('email', 'username', 'name', 'password', 'password2')

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError("Passwords do not match.")
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    class Meta:
        fields = ('email', 'password')

