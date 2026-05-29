from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from accounts.models import User
from .models import Wallet, WalletBalance
from marketplace.models import Transaction
from core.models import Currency
import uuid


@receiver(post_save, sender=User)
def create_wallet_for_user(sender, instance, created, **kwargs):
    """Create a wallet for newly created users."""
    if created:
        # Create wallet with UUID
        wallet_id = str(uuid.uuid4())
        wallet = Wallet.objects.create(
            id=wallet_id,
            user=instance
        )

        # Create wallet balances for all supported currencies
        supported_currencies = Currency.get_supported_currencies()
        for currency_code in supported_currencies:
            try:
                currency = Currency.objects.get(code=currency_code)
                WalletBalance.objects.create(
                    wallet=wallet,
                    currency=currency,
                    amount=0.00
                )
            except Currency.DoesNotExist:
                # Currency will be created during migration
                pass


@receiver(post_save, sender=Transaction)
def credit_wallet_for_completed_deposit(sender, instance, **kwargs):
    """Credit the original deposit applicant when an admin completes it."""
    from .services import credit_completed_deposit

    credit_completed_deposit(instance)

