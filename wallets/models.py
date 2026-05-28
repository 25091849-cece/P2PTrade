from django.db import models
from django.core.exceptions import ValidationError


class Wallet(models.Model):
    """User's multi-currency wallet container."""
    id = models.CharField(max_length=255, primary_key=True)
    user = models.OneToOneField('accounts.User', on_delete=models.CASCADE, related_name='wallet')
    balance_total = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    verification_failed_attempts = models.IntegerField(default=0)
    verification_locked_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wallets'
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"Wallet of {self.user.name or self.user.email}"

    def get_total_balance(self):
        """Calculate total balance across all currencies."""
        total = self.balances.aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        return total


class WalletBalance(models.Model):
    """Individual currency balance in a wallet."""
    id = models.AutoField(primary_key=True)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='balances')
    currency = models.ForeignKey('core.Currency', on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wallet_balances'
        unique_together = ('wallet', 'currency')
        indexes = [
            models.Index(fields=['wallet']),
            models.Index(fields=['currency']),
        ]

    def clean(self):
        """Validate that amount is non-negative."""
        if self.amount < 0:
            raise ValidationError('Balance cannot be negative.')

    def save(self, *args, **kwargs):
        """Save with validation."""
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.wallet.user.email} - {self.currency.code}: {self.amount}"

    def add_balance(self, amount):
        """Add amount to wallet balance."""
        if amount < 0:
            raise ValueError('Amount must be positive.')
        self.amount += amount
        self.save()
        return self.amount

    def subtract_balance(self, amount):
        """Subtract amount from wallet balance."""
        if amount < 0:
            raise ValueError('Amount must be positive.')
        if self.amount < amount:
            raise ValueError(
                f"Insufficient balance. Available: {self.amount}, Required: {amount}"
            )
        self.amount -= amount
        self.save()
        return self.amount

