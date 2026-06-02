"""
REST API Serializers for marketplace deals and transactions.
"""

from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from marketplace.models import Deal, Transaction


class DealSerializer(serializers.ModelSerializer):
    """Serializer for Deal model."""
    seller_email = serializers.CharField(source='seller.email', read_only=True)
    seller_name = serializers.CharField(source='seller.name', read_only=True)
    from_currency_code = serializers.CharField(source='from_currency.code', read_only=True)
    to_currency_code = serializers.CharField(source='to_currency.code', read_only=True)
    receive_amount = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    time_remaining_seconds = serializers.SerializerMethodField()
    time_remaining_display = serializers.SerializerMethodField()

    class Meta:
        model = Deal
        fields = (
            'id', 'seller_email', 'seller_name', 'from_currency_code', 'to_currency_code',
            'amount', 'rate', 'trend', 'status', 'receive_amount', 'is_expired',
            'time_remaining_seconds', 'time_remaining_display',
            'created_at', 'expires_at', 'accepted_at'
        )
        read_only_fields = ('id', 'seller_email', 'seller_name', 'created_at', 'expires_at', 'accepted_at')

    def get_receive_amount(self, obj):
        """Calculate receive amount for buyer."""
        return float(obj.get_receive_amount())

    def get_is_expired(self, obj):
        """Check if deal has expired."""
        return obj.is_expired()

    def get_time_remaining_seconds(self, obj):
        """Get remaining seconds until deal expires."""
        if obj.is_expired():
            return 0
        remaining = obj.expires_at - timezone.now()
        return max(0, int(remaining.total_seconds()))

    def get_time_remaining_display(self, obj):
        """Get human-readable time remaining display."""
        if obj.is_expired():
            return "Expired"
        remaining = obj.expires_at - timezone.now()
        total_seconds = int(remaining.total_seconds())

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours > 0:
            return f"{hours}h {minutes}m remaining"
        return f"{minutes}m remaining"


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for Transaction model."""
    buyer_email = serializers.CharField(source='buyer.email', read_only=True, allow_null=True)
    seller_email = serializers.CharField(source='seller.email', read_only=True, allow_null=True)
    user_email = serializers.CharField(source='user.email', read_only=True, allow_null=True)
    from_currency_code = serializers.CharField(source='from_currency.code', read_only=True)
    to_currency_code = serializers.CharField(source='to_currency.code', read_only=True)
    deal_id = serializers.IntegerField(source='deal.id', read_only=True, allow_null=True)

    class Meta:
        model = Transaction
        fields = (
            'id', 'type', 'status', 'buyer_email', 'seller_email', 'user_email',
            'from_currency_code', 'to_currency_code', 'amount', 'received_amount', 'rate',
            'payment_reference', 'deal_id', 'created_at', 'completed_at'
        )
        read_only_fields = (
            'id', 'buyer_email', 'seller_email', 'user_email', 'created_at', 'completed_at'
        )

