from django.db import models
from django.utils import timezone


class Deal(models.Model):
    """Currency exchange offers/deals in the marketplace."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('accepted', 'Accepted'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]

    TREND_CHOICES = [
        ('up', 'Up'),
        ('down', 'Down'),
    ]

    id = models.AutoField(primary_key=True)
    seller = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='created_deals')
    from_currency = models.ForeignKey('core.Currency', on_delete=models.PROTECT, related_name='deals_from')
    to_currency = models.ForeignKey('core.Currency', on_delete=models.PROTECT, related_name='deals_to')

    amount = models.DecimalField(max_digits=15, decimal_places=2)  # Quantity of from_currency
    rate = models.DecimalField(max_digits=10, decimal_places=4)  # Exchange rate offered
    trend = models.CharField(max_length=4, choices=TREND_CHOICES)  # Market trend indicator

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()  # 48 hours from creation
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'deals'
        indexes = [
            models.Index(fields=['seller']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Deal #{self.id}: {self.amount} {self.from_currency.code} → {self.to_currency.code}"

    def is_expired(self):
        """Check if deal has expired."""
        return timezone.now() > self.expires_at

    def get_receive_amount(self):
        """Calculate how much to_currency the buyer will receive."""
        return self.amount * self.rate


class Transaction(models.Model):
    """Financial transactions between users."""
    TYPE_CHOICES = [
        ('exchange', 'Exchange'),
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('offer_created', 'Offer Created'),
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('awaiting_confirmation', 'Awaiting Confirmation'),
    ]

    id = models.BigAutoField(primary_key=True)

    # Participants
    buyer = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='purchases'
    )
    seller = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sales'
    )
    user = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transactions'
    )  # For non-P2P transactions

    # Deal reference (optional, for P2P transactions)
    deal = models.ForeignKey(
        Deal, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transactions'
    )

    # Transaction details
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    from_currency = models.ForeignKey(
        'core.Currency', on_delete=models.PROTECT, related_name='transactions_from'
    )
    to_currency = models.ForeignKey(
        'core.Currency', on_delete=models.PROTECT, related_name='transactions_to'
    )

    # Amounts
    amount = models.DecimalField(max_digits=15, decimal_places=2)  # Source currency
    received_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )  # Destination currency
    rate = models.DecimalField(max_digits=10, decimal_places=4)

    # Status and verification
    status = models.CharField(max_length=25, choices=STATUS_CHOICES)
    tx_hash = models.CharField(max_length=255, null=True, blank=True)  # Mock blockchain hash

    # Payment tracking
    payment_reference = models.CharField(max_length=255, null=True, blank=True)  # P2P{timestamp}{random}
    proof_of_payment = models.TextField(null=True, blank=True)  # Base64 encoded image/document

    # Timestamps
    timestamp = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'transactions'
        indexes = [
            models.Index(fields=['buyer']),
            models.Index(fields=['seller']),
            models.Index(fields=['user']),
            models.Index(fields=['type']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['deal']),
        ]

    def __str__(self):
        if self.type in ['purchase', 'sale']:
            buyer_name = self.buyer.name or self.buyer.email if self.buyer else 'Unknown'
            seller_name = self.seller.name or self.seller.email if self.seller else 'Unknown'
            return f"TXN #{self.id}: {buyer_name} ↔ {seller_name}"
        user_name = self.user.name or self.user.email if self.user else 'Unknown'
        return f"TXN #{self.id}: {self.type} - {self.amount} {self.from_currency.code}"

    def mark_completed(self):
        """Mark transaction as completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()

