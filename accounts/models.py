from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class User(AbstractUser):
    """Custom User model for P2P Trade platform."""
    ROLE_CHOICES = [
        ('user', 'Regular User'),
        ('admin', 'Administrator'),
    ]

    name = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')

    # Security tracking
    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['username']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        return f"{self.name or self.username} ({self.email})"

    def is_account_locked(self):
        """Check if account is currently locked."""
        if self.locked_until and timezone.now() < self.locked_until:
            return True
        return False

    def increment_failed_login(self):
        """Track failed login attempts."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            # Lock account for 15 minutes
            self.locked_until = timezone.now() + timezone.timedelta(minutes=15)
        self.save()

    def reset_failed_login(self):
        """Reset failed login attempts after successful login."""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save()

    def is_admin(self):
        """Check if user has admin role."""
        return self.role == 'admin'

