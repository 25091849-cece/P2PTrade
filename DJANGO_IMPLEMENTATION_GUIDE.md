# P2P Trade Platform - Data Flow & Implementation Guide

## Core Transaction Flows

### 1. Deal Creation Flow
```
User (Seller)
    ↓ (Creates Deal with USD→MYR exchange)
    ↓
Deal (status: active, expires_at: +48hrs)
    ↓
Transaction (type: offer_created, status: pending)
    ↓
Notification (sent to seller: "Offer created")
```

**Data Changes:**
- Deal table: INSERT new record
- Transaction table: INSERT record (type='offer_created')
- Notification table: INSERT record for seller

---

### 2. Deal Acceptance Flow (Purchase)
```
Buyer User                                  Seller User
    ↓ (Accepts Deal #5)
    ├─ Wallet Check: Has enough MYR? 
    │  (If NO → Reject with error)
    │
    ├─ Create BUYER Transaction
    │  (type: purchase, status: awaiting_confirmation)
    │  amount: 100 USD → received_amount: 460 MYR (at 4.60 rate)
    │
    ├─ Create SELLER Transaction
    │  (type: sale, status: pending)
    │
    ├─ Update Deal
    │  (status: accepted, accepted_at: now)
    │
    ├─ Create Payment Reference
    │  Format: "P2P{timestamp}{random}"
    │
    └─ Notifications sent to both parties
        ├─ Seller: "Your offer accepted! Payment reference: P2P..."
        └─ Buyer: "Payment reference for your purchase: P2P..."
```

**Database Changes:**
- Deal table: UPDATE (status='accepted', accepted_at=now)
- Transaction table: INSERT 2 records (buyer purchase + seller sale)
- Wallet table: NO change (escrow during awaiting_confirmation)
- Notification table: INSERT 2 records

---

### 3. Payment Confirmation Flow
```
Buyer
    ↓ (Uploads proof of payment)
    ↓
Transaction (buyer's purchase, status: awaiting_confirmation)
    ├─ Check proof uploaded
    ├─ Update proof_of_payment field
    └─ status: pending (awaiting seller confirmation)
    
Seller receives notification
    ├─ Reviews proof
    ├─ Confirms payment received OR disputes
    │
    ├─ IF CONFIRMED:
    │  ├─ Buyer Transaction: status = completed
    │  ├─ Seller Transaction: status = completed
    │  │
    │  ├─ UPDATE Wallet Balances:
    │  │  ├─ Buyer: -460 MYR, +100 USD
    │  │  └─ Seller: -100 USD, +460 MYR
    │  │
    │  └─ Notifications:
    │     ├─ Seller: "Payment confirmed! 460 MYR received"
    │     └─ Buyer: "Exchange complete! You now have 100 USD"
    │
    └─ IF DISPUTED:
       └─ Create DISPUTE record
```

**Database Changes** (on confirmation):
- Transaction table: UPDATE both transactions (status='completed')
- WalletBalance table: UPDATE 4 records (buyer -MYR, +USD; seller -USD, +MYR)
- ActivityRecord table: INSERT 2 records
- Notification table: INSERT 2 records

---

### 4. Dispute Resolution Flow
```
Dispute Created
    ├─ Captured at: awaiting_confirmation status
    ├─ Escrow: Funds held in limbo
    └─ Status: pending
    
Admin Reviews Dispute
    ├─ Reads: Evidence, messages, activity logs
    ├─ Contacts both parties if needed
    └─ status: under_review
    
Admin Resolves
    ├─ Choose resolution type:
    │  ├─ release_to_buyer (100%): Buyer gets USD, Seller loses MYR
    │  ├─ return_to_seller (100%): Seller gets USD back, Buyer loses MYR
    │  └─ partial_split (custom split): e.g., 70% buyer, 30% seller
    │
    ├─ CREATE DisputeResolution record
    ├─ UPDATE Wallet balances based on resolution type
    ├─ Mark both Transactions as completed
    ├─ Update Dispute status: resolved
    │
    └─ Notifications:
       ├─ Buyer: "Dispute resolved: [resolution details]"
       └─ Seller: "Dispute resolved: [resolution details]"
```

**Database Changes** (on resolution):
- Dispute table: UPDATE (status='resolved', resolved_at=now)
- DisputeResolution table: INSERT record
- WalletBalance table: UPDATE 2-4 records (based on resolution)
- Transaction table: UPDATE both transactions (status='completed')
- DisputeActivityLog table: INSERT record
- Notification table: INSERT 2 records

---

## Critical Business Rules

### Balance Verification
```python
# Before any withdrawal/purchase
def verify_balance(user, currency, amount):
    wallet_balance = WalletBalance.objects.get(
        wallet__user=user,
        currency=currency
    )
    if wallet_balance.amount < amount:
        raise InsufficientBalanceError(
            f"Need {amount} {currency}, have {wallet_balance.amount}"
        )
    return True
```

### Account Lock Mechanism
```python
# After failed login
def handle_failed_login(user):
    user.failed_login_attempts += 1
    
    if user.failed_login_attempts >= 5:
        # Lock for 15 minutes
        user.locked_until = now() + timedelta(minutes=15)
    
    user.save()

# Before login attempt
def can_login(user):
    if user.locked_until and now() < user.locked_until:
        remaining = (user.locked_until - now()).seconds // 60
        raise AccountLockedException(
            f"Account locked for {remaining} more minutes"
        )
    return True
```

### Deal Expiry
```python
# Cleanup task (run hourly or daily)
def expire_old_deals():
    expired = Deal.objects.filter(
        status='active',
        expires_at__lt=now()
    )
    for deal in expired:
        deal.status = 'expired'
        deal.save()
        
        # Notify seller
        Notification.objects.create(
            user=deal.seller,
            notification_type='deal_expired',
            message=f'Your deal #{deal.id} has expired'
        )
```

### Escrow Logic
```python
# When deal accepted, funds enter escrow
def enter_escrow(buyer_transaction, seller_transaction):
    # Funds are reserved but not yet transferred
    # buyer_transaction.status = 'awaiting_confirmation'
    # seller_transaction.status = 'pending'
    # These transactions don't update wallet balances yet
    pass

# When payment confirmed by seller
def release_from_escrow(dispute_resolution_type):
    if dispute_resolution_type == 'release_to_buyer':
        # Full release to buyer: buyer gets currency, seller gets paid
        buyer_wallet.amount += received_amount
        seller_wallet.amount += myr_payment
        
    elif dispute_resolution_type == 'return_to_seller':
        # Return to seller: seller gets currency back, buyer loses payment
        seller_wallet.amount += original_amount
        buyer_wallet.amount -= myr_payment
        
    elif dispute_resolution_type == 'partial_split':
        # Custom split
        buyer_wallet.amount += (received_amount * split_percent_buyer)
        seller_wallet.amount += (myr_payment * split_percent_seller)
```

---

## Data Validation Rules

| Field | Validation | Error |
|-------|-----------|-------|
| User.email | Unique, valid email format | `ValidationError` |
| User.name | Non-empty, max 255 chars | `ValidationError` |
| Deal.amount | > 0, decimal places ≤ 2 | `ValidationError` |
| Deal.rate | > 0, decimal places ≤ 4 | `ValidationError` |
| Transaction.amount | > 0, matches wallet balance | `InsufficientBalanceError` |
| Dispute.reason | Non-empty, min 10 chars | `ValidationError` |
| WalletBalance.amount | ≥ 0 (non-negative) | `ValidationError` |

---

## Query Optimization Tips

### High-Frequency Queries
```python
# User dashboard transactions (optimize with select_related)
Transaction.objects.filter(
    Q(buyer=user) | Q(seller=user)
).select_related(
    'buyer', 'seller', 'from_currency', 'to_currency', 'deal'
).prefetch_related('dispute')

# Wallet balance for all currencies
wallet = Wallet.objects.get(user=user)
balances = wallet.balances.select_related('currency')

# Active deals with seller info
Deal.objects.filter(
    status='active',
    expires_at__gt=now()
).select_related('seller', 'from_currency', 'to_currency')

# Dispute with all related data
Dispute.objects.select_related(
    'transaction', 'buyer', 'seller', 'raised_by'
).prefetch_related('messages', 'activity_logs')
```

### Aggregation Queries
```python
# Total volume traded
from django.db.models import Sum, DecimalField

total_myr_volume = Transaction.objects.filter(
    status='completed'
).aggregate(
    total=Sum('myr_amount', output_field=DecimalField())
)['total']

# Active deals per seller
from django.db.models import Count

seller_stats = User.objects.annotate(
    active_deals=Count('created_deals', filter=Q(created_deals__status='active'))
)
```

---

## API Endpoints (Suggested)

### Authentication
- `POST /api/auth/register` - Create new account
- `POST /api/auth/login` - Login user
- `POST /api/auth/logout` - Logout user
- `GET /api/auth/me` - Get current user

### Deals
- `GET /api/deals` - List all active deals (with filters)
- `GET /api/deals/<id>` - Get deal details
- `POST /api/deals` - Create new deal
- `POST /api/deals/<id>/accept` - Accept deal
- `DELETE /api/deals/<id>` - Cancel deal

### Transactions
- `GET /api/transactions` - List user transactions
- `GET /api/transactions/<id>` - Get transaction details
- `POST /api/transactions/<id>/confirm-payment` - Submit proof of payment
- `POST /api/transactions/<id>/confirm-received` - Confirm payment received

### Disputes
- `GET /api/disputes` - List all disputes (admin only)
- `GET /api/disputes/<id>` - Get dispute details
- `POST /api/disputes` - Raise new dispute
- `POST /api/disputes/<id>/message` - Add message to dispute
- `POST /api/disputes/<id>/resolve` - Resolve dispute (admin only)

### Wallet
- `GET /api/wallet` - Get wallet info & balances
- `GET /api/wallet/history` - Get transaction history
- `POST /api/wallet/deposit` - Add funds
- `POST /api/wallet/withdraw` - Withdraw funds

### Admin
- `GET /api/admin/users` - List all users (admin only)
- `GET /api/admin/transactions` - List all transactions (admin only)
- `GET /api/admin/disputes` - List all disputes (admin only)
- `GET /api/admin/stats` - Platform statistics (admin only)

---

## Recommended Django Packages

```python
# settings.py INSTALLED_APPS
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party
    'rest_framework',           # API endpoints
    'rest_framework.authtoken', # Token auth
    'corsheaders',              # CORS for React
    'django_filters',           # Filtering
    'drf_spectacular',          # API documentation
    'celery',                   # Async tasks (deal expiry, notifications)
    'django_extensions',        # Dev tools
    
    # Your apps
    'accounts',                 # User models
    'marketplace',              # Deal, Transaction models
    'disputes',                 # Dispute models
    'wallets',                  # Wallet models
    'notifications',            # Notification models
]
```

---

## Asynchronous Tasks (Celery/Background Jobs)

```python
# tasks.py
from celery import shared_task

@shared_task
def expire_deals():
    """Run hourly to expire old deals"""
    Deal.objects.filter(
        status='active',
        expires_at__lt=now()
    ).update(status='expired')

@shared_task
def send_notification_email(notification_id):
    """Send email for important notifications"""
    notification = Notification.objects.get(id=notification_id)
    if notification.notification_type in [
        'dispute_raised', 'dispute_resolved', 'payment_confirmed'
    ]:
        send_email_notification(notification)

@shared_task
def unlock_accounts():
    """Run every minute to unlock accounts after 15 min lock period"""
    User.objects.filter(
        locked_until__lt=now(),
        locked_until__isnull=False
    ).update(
        locked_until=None,
        failed_login_attempts=0
    )
```

---

## Testing Recommendations

```python
# tests/test_transactions.py
class TransactionTestCase(TestCase):
    def test_deal_acceptance_creates_transactions(self):
        """Test that accepting a deal creates both buyer and seller transactions"""
        
    def test_insufficient_balance_rejected(self):
        """Test that buyers with insufficient balance can't accept deals"""
        
    def test_payment_confirmation_updates_balances(self):
        """Test that confirming payment transfers currencies"""
        
    def test_dispute_escrows_funds(self):
        """Test that disputed transactions don't update balances until resolved"""

class DisputeTestCase(TestCase):
    def test_full_release_to_buyer(self):
        """Test 100% release to buyer resolution"""
        
    def test_partial_split_resolution(self):
        """Test custom split resolution"""

class WalletTestCase(TestCase):
    def test_multi_currency_balance(self):
        """Test that wallet correctly handles 11 currencies"""
        
    def test_insufficient_balance_error(self):
        """Test that withdrawals are blocked if insufficient balance"""
```

---

## Data Migration from React (localStorage → PostgreSQL)

```python
# management/commands/migrate_from_react.py
from django.core.management.base import BaseCommand
import json

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('json_file', type=str)

    def handle(self, *args, **options):
        with open(options['json_file']) as f:
            data = json.load(f)
        
        # Migrate users
        for user_data in data['users']:
            User.objects.create(
                id=user_data['id'],
                email=user_data['email'],
                name=user_data['name'],
                role=user_data['role']
            )
        
        # Migrate deals, transactions, disputes, etc.
        self.stdout.write(f"✓ Migrated {len(data['users'])} users")
```

---

**Reference Document for Django Implementation**
**Generated**: May 2026
