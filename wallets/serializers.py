"""
REST API Serializers for wallets and balances.
"""

from rest_framework import serializers
from wallets.models import Wallet, WalletBalance


class WalletBalanceSerializer(serializers.ModelSerializer):
    """Serializer for individual wallet balances."""
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    currency_name = serializers.CharField(source='currency.name', read_only=True)
    currency_symbol = serializers.CharField(source='currency.symbol', read_only=True)

    class Meta:
        model = WalletBalance
        fields = ('id', 'currency_code', 'currency_name', 'currency_symbol', 'amount', 'last_updated')
        read_only_fields = ('id', 'last_updated')


class WalletSerializer(serializers.ModelSerializer):
    """Serializer for Wallet model with nested balances."""
    balances = WalletBalanceSerializer(many=True, read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    total_balance_usd = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = ('id', 'user_email', 'balance_total', 'total_balance_usd', 'balances', 'created_at', 'updated_at')
        read_only_fields = ('id', 'user_email', 'created_at', 'updated_at')

    def get_total_balance_usd(self, obj):
        """Calculate approximate USD equivalent of total balance."""
        # Simplified calculation - in production use ExchangeRate model
        return obj.get_total_balance() * 0.217  # Approximate MYR to USD conversion

