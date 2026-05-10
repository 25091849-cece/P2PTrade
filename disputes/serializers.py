"""
REST API Serializers for disputes and resolutions.
"""

from rest_framework import serializers
from disputes.models import Dispute, DisputeResolution, DisputeMessage, DisputeActivityLog


class DisputeMessageSerializer(serializers.ModelSerializer):
    """Serializer for dispute messages."""
    sender_email = serializers.CharField(source='sender.email', read_only=True)

    class Meta:
        model = DisputeMessage
        fields = ('id', 'sender_email', 'message', 'is_admin_message', 'created_at')
        read_only_fields = ('id', 'sender_email', 'created_at')


class DisputeActivityLogSerializer(serializers.ModelSerializer):
    """Serializer for dispute activity logs."""
    actor_email = serializers.CharField(source='actor.email', read_only=True, allow_null=True)

    class Meta:
        model = DisputeActivityLog
        fields = ('id', 'actor_email', 'action', 'timestamp')
        read_only_fields = ('id', 'actor_email', 'timestamp')


class DisputeResolutionSerializer(serializers.ModelSerializer):
    """Serializer for dispute resolutions."""
    admin_email = serializers.CharField(source='resolved_by_admin.email', read_only=True, allow_null=True)

    class Meta:
        model = DisputeResolution
        fields = (
            'id', 'resolution_type', 'buyer_refund_amount', 'seller_refund_amount',
            'resolution_notes', 'admin_email', 'resolved_at'
        )
        read_only_fields = ('id', 'admin_email', 'resolved_at')


class DisputeSerializer(serializers.ModelSerializer):
    """Serializer for Dispute model."""
    buyer_email = serializers.CharField(source='buyer.email', read_only=True)
    seller_email = serializers.CharField(source='seller.email', read_only=True)
    raised_by_email = serializers.CharField(source='raised_by.email', read_only=True, allow_null=True)
    from_currency_code = serializers.CharField(source='from_currency.code', read_only=True)
    to_currency_code = serializers.CharField(source='to_currency.code', read_only=True)
    messages = DisputeMessageSerializer(many=True, read_only=True)
    activity_logs = DisputeActivityLogSerializer(many=True, read_only=True)
    resolution = DisputeResolutionSerializer(read_only=True)

    class Meta:
        model = Dispute
        fields = (
            'id', 'transaction', 'buyer_email', 'seller_email', 'raised_by_email',
            'from_currency_code', 'to_currency_code', 'foreign_amount', 'myr_amount',
            'reason', 'status', 'evidence', 'seller_confirmation_status',
            'messages', 'activity_logs', 'resolution', 'created_at', 'resolved_at'
        )
        read_only_fields = (
            'id', 'transaction', 'buyer_email', 'seller_email', 'raised_by_email',
            'messages', 'activity_logs', 'resolution', 'created_at', 'resolved_at'
        )

