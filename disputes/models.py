from django.db import models
from django.utils import timezone


class Dispute(models.Model):
    """Dispute cases between buyers and sellers."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('resolved', 'Resolved'),
    ]

    id = models.AutoField(primary_key=True)
    transaction = models.OneToOneField(
        'marketplace.Transaction', on_delete=models.CASCADE, related_name='dispute'
    )

    # Participants
    buyer = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='disputes_as_buyer'
    )
    seller = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='disputes_as_seller'
    )
    raised_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='disputes_raised',
        help_text='Either buyer or seller who raised the dispute'
    )

    # Dispute details
    from_currency = models.ForeignKey(
        'core.Currency', on_delete=models.PROTECT, related_name='disputes_from'
    )
    to_currency = models.ForeignKey(
        'core.Currency', on_delete=models.PROTECT, related_name='disputes_to'
    )

    # Amounts in dispute
    foreign_amount = models.DecimalField(max_digits=15, decimal_places=2)
    myr_amount = models.DecimalField(max_digits=15, decimal_places=2)

    # Dispute information
    reason = models.TextField()  # Dispute description
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Evidence
    evidence = models.TextField(null=True, blank=True)  # Description or base64 encoded
    seller_confirmation_status = models.CharField(max_length=100, null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'disputes'
        indexes = [
            models.Index(fields=['transaction']),
            models.Index(fields=['buyer']),
            models.Index(fields=['seller']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Dispute #{self.id}: {self.buyer.email} vs {self.seller.email}"

    def mark_under_review(self):
        """Change dispute status to under_review."""
        self.status = 'under_review'
        self.save()


class DisputeResolution(models.Model):
    """Resolution details for disputes."""
    RESOLUTION_TYPE_CHOICES = [
        ('release_to_buyer', 'Release to Buyer'),
        ('return_to_seller', 'Return to Seller'),
        ('partial_split', 'Partial Split'),
    ]

    id = models.AutoField(primary_key=True)
    dispute = models.OneToOneField(
        Dispute, on_delete=models.CASCADE, related_name='resolution'
    )

    resolution_type = models.CharField(max_length=20, choices=RESOLUTION_TYPE_CHOICES)
    buyer_refund_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    seller_refund_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )

    resolution_notes = models.TextField()
    resolved_by_admin = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        limit_choices_to={'role': 'admin'},
        related_name='dispute_resolutions'
    )

    resolved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dispute_resolutions'
        indexes = [
            models.Index(fields=['dispute']),
            models.Index(fields=['resolved_by_admin']),
        ]

    def __str__(self):
        return f"Resolution for Dispute #{self.dispute.id}: {self.resolution_type}"


class DisputeMessage(models.Model):
    """Communication thread in disputes."""
    id = models.AutoField(primary_key=True)
    dispute = models.ForeignKey(
        Dispute, on_delete=models.CASCADE, related_name='messages'
    )
    sender = models.ForeignKey('accounts.User', on_delete=models.CASCADE)

    message = models.TextField()
    is_admin_message = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dispute_messages'
        indexes = [
            models.Index(fields=['dispute']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['created_at']

    def __str__(self):
        return f"Message from {self.sender.email} in Dispute #{self.dispute.id}"


class DisputeActivityLog(models.Model):
    """Audit trail of dispute actions."""
    id = models.AutoField(primary_key=True)
    dispute = models.ForeignKey(
        Dispute, on_delete=models.CASCADE, related_name='activity_logs'
    )
    actor = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)

    action = models.TextField()  # Description of action taken

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dispute_activity_logs'
        indexes = [
            models.Index(fields=['dispute']),
            models.Index(fields=['timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f"Log for Dispute #{self.dispute.id}: {self.action}"

