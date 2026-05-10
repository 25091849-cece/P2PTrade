"""
REST API Serializers for notifications.
"""

from rest_framework import serializers
from notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model."""
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = Notification
        fields = (
            'id', 'user_email', 'notification_type', 'message',
            'related_id', 'is_read', 'created_at'
        )
        read_only_fields = ('id', 'user_email', 'created_at')

