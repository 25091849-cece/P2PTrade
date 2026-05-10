"""
REST API Serializers for core models.
"""

from rest_framework import serializers
from core.models import Currency, ExchangeRate, ActivityRecord


class CurrencySerializer(serializers.ModelSerializer):
    """Serializer for Currency model."""

    class Meta:
        model = Currency
        fields = ('code', 'name', 'symbol')
        read_only_fields = ('code', 'name', 'symbol')


class ExchangeRateSerializer(serializers.ModelSerializer):
    """Serializer for ExchangeRate model."""
    from_currency_code = serializers.CharField(source='from_currency.code', read_only=True)
    to_currency_code = serializers.CharField(source='to_currency.code', read_only=True)

    class Meta:
        model = ExchangeRate
        fields = (
            'id', 'from_currency_code', 'to_currency_code',
            'rate', 'change_percent', 'last_updated'
        )
        read_only_fields = ('id', 'from_currency_code', 'to_currency_code', 'last_updated')


class ActivityRecordSerializer(serializers.ModelSerializer):
    """Serializer for ActivityRecord model."""
    user_email = serializers.CharField(source='user.email', read_only=True)
    from_currency_code = serializers.CharField(source='from_currency.code', read_only=True, allow_null=True)
    to_currency_code = serializers.CharField(source='to_currency.code', read_only=True, allow_null=True)

    class Meta:
        model = ActivityRecord
        fields = (
            'id', 'user_email', 'activity_type', 'from_currency_code',
            'to_currency_code', 'amount', 'timestamp'
        )
        read_only_fields = ('id', 'user_email', 'timestamp')

