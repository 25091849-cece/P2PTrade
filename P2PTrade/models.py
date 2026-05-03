from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """Store additional user account data like starting balances and account info."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    balance_myr = models.CharField(max_length=50, default='RM45,000')
    balance_usd = models.CharField(max_length=50, default='$10,000')
    total_balance_usd = models.FloatField(default=104540.00)
    active_trades = models.IntegerField(default=24)
    monthly_profit_usd = models.FloatField(default=3240.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name or self.user.username}'s Profile"

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

