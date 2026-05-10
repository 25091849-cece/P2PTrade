from django.db import models


class Notification(models.Model):
    """User notifications for important events."""
    NOTIFICATION_TYPES = [
        ('deal_accepted', 'Deal Accepted'),
        ('payment_confirmed', 'Payment Confirmed'),
        ('dispute_raised', 'Dispute Raised'),
        ('dispute_resolved', 'Dispute Resolved'),
        ('transaction_completed', 'Transaction Completed'),
        ('transaction_failed', 'Transaction Failed'),
        ('account_locked', 'Account Locked'),
        ('deal_expired', 'Deal Expired'),
    ]

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='notifications'
    )

    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    message = models.TextField()

    related_id = models.IntegerField(null=True, blank=True)  # Transaction or Dispute ID
    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['is_read']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.email}: {self.notification_type}"

    def mark_as_read(self):
        """Mark notification as read."""
        self.is_read = True
        self.save()

