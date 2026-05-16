# P2P Trade Platform - Django Data Models

## Overview
This document provides the complete data model structure extracted from your React project, ready for Django implementation. The platform is a peer-to-peer currency exchange marketplace with dispute resolution, multi-currency wallets, and admin controls.

---

## Entity Relationship Overview

### Main Entities:
1. **USER** - Platform users (buyers, sellers, admins)
2. **WALLET** - User's multi-currency wallet container
3. **WALLET_BALANCE** - Individual currency balance (11 supported)
4. **CURRENCY** - Supported currencies (MYR, USD, EUR, GBP, JPY, AUD, CAD, CHF, CNY, HKD, NZD)
5. **DEAL** - Marketplace currency exchange offers
6. **TRANSACTION** - All financial transactions (P2P trades, deposits, withdrawals)
7. **DISPUTE** - Dispute cases between buyers and sellers
8. **DISPUTE_RESOLUTION** - Resolution details for disputes
9. **DISPUTE_MESSAGE** - Communication thread in disputes
10. **DISPUTE_ACTIVITY_LOG** - Audit trail of dispute actions
11. **NOTIFICATION** - User notifications
12. **EXCHANGE_RATE** - Currency exchange rates
13. **ACTIVITY_RECORD** - User activity history

---

## Django Models

### 1. USER Model
```python
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    ROLE_CHOICES = [
        ('user', 'Regular User'),
        ('admin', 'Administrator'),
    ]
    
    id = models.CharField(max_length=255, primary_key=True, unique=True)  # UUID or timestamp-based
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    password_hash = models.CharField(max_length=500)
    
    # Security tracking
    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['username']),
            models.Index(fields=['role']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.email})"
    
    def is_account_locked(self):
        """Check if account is currently locked"""
        if self.locked_until and timezone.now() < self.locked_until:
            return True
        return False
    
    def increment_failed_login(self):
        """Track failed login attempts"""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            # Lock account for 15 minutes
            self.locked_until = timezone.now() + timezone.timedelta(minutes=15)
        self.save()
    
    def reset_failed_login(self):
        """Reset failed login attempts after successful login"""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save()
```

---

### 2. WALLET Model
```python
class Wallet(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance_total = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'wallets'
        indexes = [
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"Wallet of {self.user.name}"
    
    def get_total_balance(self):
        """Calculate total balance across all currencies"""
        total = self.balances.aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        return total
```

---

### 3. CURRENCY Model
```python
class Currency(models.Model):
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
        """Get list of all 11 supported currencies"""
        return [
            'MYR', 'USD', 'EUR', 'GBP', 'JPY', 'AUD', 
            'CAD', 'CHF', 'CNY', 'HKD', 'NZD'
        ]
```

---

### 4. WALLET_BALANCE Model
```python
class WalletBalance(models.Model):
    id = models.AutoField(primary_key=True)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='balances')
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'wallet_balances'
        unique_together = ('wallet', 'currency')
        indexes = [
            models.Index(fields=['wallet']),
            models.Index(fields=['currency']),
        ]
    
    def __str__(self):
        return f"{self.wallet.user.name} - {self.currency.code}: {self.amount}"
    
    def add_balance(self, amount):
        """Add amount to wallet balance"""
        self.amount += amount
        self.save()
        return self.amount
    
    def subtract_balance(self, amount):
        """Subtract amount from wallet balance"""
        if self.amount >= amount:
            self.amount -= amount
            self.save()
            return self.amount
        raise ValueError(f"Insufficient balance. Available: {self.amount}, Required: {amount}")
```

---

### 5. DEAL Model
```python
class Deal(models.Model):
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
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_deals')
    from_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name='deals_from')
    to_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name='deals_to')
    
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
        """Check if deal has expired"""
        return timezone.now() > self.expires_at
    
    def get_receive_amount(self):
        """Calculate how much to_currency the buyer will receive"""
        return self.amount * self.rate
```

---

### 6. TRANSACTION Model
```python
class Transaction(models.Model):
    TYPE_CHOICES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('sell', 'Sell'),
        ('buy', 'Buy'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('awaiting_confirmation', 'Awaiting Confirmation'),
    ]
    
    id = models.BigAutoField(primary_key=True)  # Timestamp-based ID
    
    # Participants
    buyer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='purchases'
    )
    seller = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sales'
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
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
        Currency, on_delete=models.PROTECT, related_name='transactions_from'
    )
    to_currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT, related_name='transactions_to'
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
            return f"TXN #{self.id}: {self.buyer.name} ↔ {self.seller.name}"
        return f"TXN #{self.id}: {self.type} - {self.amount} {self.from_currency.code}"
    
    def mark_completed(self):
        """Mark transaction as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
```

---

### 7. DISPUTE Model
```python
class Dispute(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('resolved', 'Resolved'),
    ]
    
    id = models.AutoField(primary_key=True)
    transaction = models.OneToOneField(
        Transaction, on_delete=models.CASCADE, related_name='dispute'
    )
    
    # Participants
    buyer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='disputes_as_buyer'
    )
    seller = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='disputes_as_seller'
    )
    raised_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='disputes_raised', 
        help_text='Either buyer or seller who raised the dispute'
    )
    
    # Dispute details
    from_currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT, related_name='disputes_from'
    )
    to_currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT, related_name='disputes_to'
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
        return f"Dispute #{self.id}: {self.buyer.name} vs {self.seller.name}"
    
    def mark_under_review(self):
        """Change dispute status to under_review"""
        self.status = 'under_review'
        self.save()
```

---

### 8. DISPUTE_RESOLUTION Model
```python
class DisputeResolution(models.Model):
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
        User, on_delete=models.SET_NULL, null=True,
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
```

---

### 9. DISPUTE_MESSAGE Model
```python
class DisputeMessage(models.Model):
    id = models.AutoField(primary_key=True)
    dispute = models.ForeignKey(
        Dispute, on_delete=models.CASCADE, related_name='messages'
    )
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    
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
        return f"Message from {self.sender.name} in Dispute #{self.dispute.id}"
```

---

### 10. DISPUTE_ACTIVITY_LOG Model
```python
class DisputeActivityLog(models.Model):
    id = models.AutoField(primary_key=True)
    dispute = models.ForeignKey(
        Dispute, on_delete=models.CASCADE, related_name='activity_logs'
    )
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
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
```

---

### 11. NOTIFICATION Model
```python
class Notification(models.Model):
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
        User, on_delete=models.CASCADE, related_name='notifications'
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
        return f"Notification for {self.user.name}: {self.notification_type}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.save()
```

---

### 12. EXCHANGE_RATE Model
```python
class ExchangeRate(models.Model):
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
```

---

### 13. ACTIVITY_RECORD Model
```python
class ActivityRecord(models.Model):
    ACTIVITY_TYPES = [
        ('exchange', 'Exchange'),
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
    ]
    
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='activity_records'
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
```

---

## Database Relationships Summary

| Relationship | Type | Notes |
|---|---|---|
| User → Wallet | 1:1 | One-to-one, auto-created with user |
| Wallet → WalletBalance | 1:many | Multiple currencies per wallet |
| WalletBalance → Currency | many:1 | Each currency has multiple balances |
| User → Deal | 1:many | User creates deals as seller |
| Deal → Transaction | 1:many | Deal generates 2 transactions (buy+sell) |
| User → Transaction | many:many | Buyer and seller relationships |
| Transaction → Dispute | 1:1 | Max one dispute per transaction |
| Dispute → User | many:2 | Buyer and seller involved |
| Dispute → Message | 1:many | Multiple messages per dispute |
| Dispute → ActivityLog | 1:many | Audit trail per dispute |
| Dispute → Resolution | 1:1 | Resolution details |
| User → Notification | 1:many | Multiple notifications per user |
| User → ExchangeRate | many:1 | Used to display rates |
| User → ActivityRecord | 1:many | User activity history |

---

## Key Constraints & Business Rules

1. **Currency Support**: Only 11 currencies allowed (MYR, USD, EUR, GBP, JPY, AUD, CAD, CHF, CNY, HKD, NZD)
2. **Account Lock**: After 5 failed login attempts, account locked for 15 minutes
3. **Deal Expiry**: Deals expire 48 hours after creation
4. **Role-based Access**: Only 'admin' role can resolve disputes
5. **Dispute Isolation**: One transaction can only have one active dispute
6. **Balance Integrity**: WalletBalance amounts cannot go negative (validated at application level)
7. **Unique Constraints**:
   - User.email is unique
   - User.username is unique
   - WalletBalance (wallet_id, currency_code) is unique
   - ExchangeRate (from_currency, to_currency) is unique

---

## Indexes for Performance

All tables have appropriate indexes on:
- Foreign keys
- Frequently filtered fields (status, type, role)
- Timestamp fields (created_at, expires_at)
- User lookups

---

## Django Models File Template

Create `models.py` with all above models or split into:
- `models/user.py`
- `models/wallet.py`
- `models/transaction.py`
- `models/dispute.py`
- `models/notification.py`
- `models/currency.py`

---

## Initial Data to Populate

```python
# Currencies to be created
CURRENCIES = [
    {'code': 'MYR', 'name': 'Malaysian Ringgit', 'symbol': 'RM'},
    {'code': 'USD', 'name': 'US Dollar', 'symbol': '$'},
    {'code': 'EUR', 'name': 'Euro', 'symbol': '€'},
    {'code': 'GBP', 'name': 'British Pound', 'symbol': '£'},
    {'code': 'JPY', 'name': 'Japanese Yen', 'symbol': '¥'},
    {'code': 'AUD', 'name': 'Australian Dollar', 'symbol': 'A$'},
    {'code': 'CAD', 'name': 'Canadian Dollar', 'symbol': 'C$'},
    {'code': 'CHF', 'name': 'Swiss Franc', 'symbol': 'CHF'},
    {'code': 'CNY', 'name': 'Chinese Yuan', 'symbol': '¥'},
    {'code': 'HKD', 'name': 'Hong Kong Dollar', 'symbol': 'HK$'},
    {'code': 'NZD', 'name': 'New Zealand Dollar', 'symbol': 'NZ$'},
]
```

---

## Migration Strategy

1. Create all models
2. Create initial migrations: `python manage.py makemigrations`
3. Create exchange rates: `python manage.py migrate`
4. Populate currencies fixture or create management command
5. Create superuser: `python manage.py createsuperuser`

---

**Generated**: Based on React P2P Trade Platform analysis (May 2026)
