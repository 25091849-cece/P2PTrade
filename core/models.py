from django.db import models
from django.utils import timezone


class Currency(models.Model):
    """Supported currencies for the P2P trading platform."""
    code = models.CharField(max_length=3, primary_key=True)  # MYR, USD, EUR, etc.
    name = models.CharField(max_length=100)  # Malaysian Ringgit, US Dollar, Euro
    symbol = models.CharField(max_length=5)  # RM, $, €, etc.

    class Meta:
        db_table = 'currencies'
        verbose_name_plural = 'Currencies'

    def __str__(self):
        return f"{self.code} - {self.name}"

    @staticmethod
    def get_supported_currencies():
        """Get list of all 11 supported currencies."""
        return [
            'MYR', 'USD', 'EUR', 'GBP', 'JPY', 'AUD',
            'CAD', 'CHF', 'CNY', 'HKD', 'NZD'
        ]


class ExchangeRate(models.Model):
    """Exchange rates between currency pairs."""
    id = models.AutoField(primary_key=True)
    from_currency = models.ForeignKey(
        Currency, on_delete=models.CASCADE, related_name='exchange_rates_from'
    )
    to_currency = models.ForeignKey(
        Currency, on_delete=models.CASCADE, related_name='exchange_rates_to'
    )

    rate = models.DecimalField(max_digits=10, decimal_places=4)
    change_percent = models.DecimalField(
        max_digits=5, decimal_places=2, help_text='Percentage change indicator'
    )

    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'exchange_rates'
        unique_together = ('from_currency', 'to_currency')
        indexes = [
            models.Index(fields=['from_currency']),
            models.Index(fields=['to_currency']),
        ]

    def __str__(self):
        return f"{self.from_currency.code} → {self.to_currency.code}: {self.rate}"


class ActivityRecord(models.Model):
    """User activity history for audit trails."""
    ACTIVITY_TYPES = [
        ('exchange', 'Exchange'),
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
    ]

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='activity_records'
    )

    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    from_currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT,
        related_name='activities_from', null=True, blank=True
    )
    to_currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT,
        related_name='activities_to', null=True, blank=True
    )

    amount = models.DecimalField(max_digits=15, decimal_places=2)

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'activity_records'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['activity_type']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.name}: {self.activity_type} - {self.amount}"

