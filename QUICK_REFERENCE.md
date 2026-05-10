# P2P Trade Platform - Quick Reference Guide

**Last Updated:** May 10, 2026  
**Implementation Status:** ✅ COMPLETE - Phases 1-3

---

## Quick Start

### 1. Development Server
```bash
cd C:\Users\Asus\Documents\GitHub\P2PTrade
python manage.py runserver
# Access at http://localhost:8000
# Admin at http://localhost:8000/admin/
```

### 2. Admin Credentials
```
Email: admin@p2ptrade.com
Password: Admin@123456
```

### 3. Available Admin Pages
- `/admin/accounts/user/` - Users
- `/admin/core/currency/` - Currencies (11 total)
- `/admin/core/exchangerate/` - Exchange rates (24 pairs)
- `/admin/wallets/wallet/` - Wallets
- `/admin/wallets/walletbalance/` - Wallet balances
- `/admin/marketplace/deal/` - Deals
- `/admin/marketplace/transaction/` - Transactions
- `/admin/disputes/dispute/` - Disputes
- `/admin/notifications/notification/` - Notifications

---

## Database Schema Summary

### Users (Custom)
```sql
users {
  id, email (unique), username (unique), name, role,
  password, is_active, is_staff, is_superuser,
  failed_login_attempts, locked_until,
  created_at, updated_at
}
```

### Wallets & Balances
```sql
wallets {
  id (UUID), user_id (FK, one-to-one),
  balance_total, created_at, updated_at
}

wallet_balances {
  id, wallet_id (FK), currency_code (FK),
  amount, last_updated
}
```

### Currencies
```sql
currencies {
  code (PK: MYR, USD, EUR, ...),
  name, symbol
}

exchange_rates {
  id, from_currency (FK), to_currency (FK),
  rate, change_percent, last_updated
}
```

### Marketplace
```sql
deals {
  id, seller_id (FK), from_currency (FK), to_currency (FK),
  amount, rate, trend (up/down),
  status (active/accepted/expired/cancelled),
  created_at, expires_at, accepted_at
}

transactions {
  id, buyer_id (FK), seller_id (FK), user_id (FK),
  deal_id (FK), type, status,
  from_currency (FK), to_currency (FK),
  amount, received_amount, rate,
  payment_reference, proof_of_payment,
  created_at, completed_at
}
```

### Disputes
```sql
disputes {
  id, transaction_id (FK, one-to-one),
  buyer_id (FK), seller_id (FK), raised_by_id (FK),
  from_currency (FK), to_currency (FK),
  foreign_amount, myr_amount,
  reason, evidence, status,
  seller_confirmation_status,
  created_at, resolved_at
}

dispute_resolutions {
  id, dispute_id (FK, one-to-one),
  resolution_type, buyer_refund_amount, seller_refund_amount,
  resolution_notes, resolved_by_admin_id (FK),
  resolved_at
}

dispute_messages {
  id, dispute_id (FK), sender_id (FK),
  message, is_admin_message, created_at
}

dispute_activity_logs {
  id, dispute_id (FK), actor_id (FK),
  action, timestamp
}
```

### Notifications & Activity
```sql
notifications {
  id, user_id (FK), notification_type,
  message, related_id, is_read, created_at
}

activity_records {
  id, user_id (FK),
  activity_type (exchange/deposit/withdrawal),
  from_currency (FK), to_currency (FK),
  amount, timestamp
}
```

---

## Key Model Methods

### User Model
```python
user.is_account_locked()  # Returns: bool
user.increment_failed_login()  # Increments, locks after 5
user.reset_failed_login()  # Resets to 0
user.is_admin()  # Returns: bool (role == 'admin')
```

### Wallet Model
```python
wallet.get_total_balance()  # Returns: sum of all balances
```

### WalletBalance Model
```python
balance.add_balance(amount)  # Returns: new amount
balance.subtract_balance(amount)  # Returns: new amount, raises if insufficient
```

### Deal Model
```python
deal.is_expired()  # Returns: bool (now > expires_at)
deal.get_receive_amount()  # Returns: amount * rate
```

### Transaction Model
```python
transaction.mark_completed()  # Sets status='completed', completed_at=now
```

### Dispute Model
```python
dispute.mark_under_review()  # Sets status='under_review'
```

### Notification Model
```python
notification.mark_as_read()  # Sets is_read=True
```

---

## Service Layer & Business Logic

### marketplace/services.py

#### DealService
```python
DealService.create_deal(
    seller, from_currency, to_currency,
    amount, rate, trend
) -> Deal

DealService.accept_deal(deal, buyer) -> (buyer_txn, seller_txn)
```

#### PaymentService
```python
PaymentService.confirm_payment(transaction, proof_of_payment) -> Transaction

PaymentService.confirm_payment_received(buyer_txn, seller_user) -> (buyer_txn, seller_txn)
```

#### DisputeService
```python
DisputeService.create_dispute(
    transaction, buyer, seller, reason, evidence=None
) -> Dispute

DisputeService.resolve_dispute(
    dispute, resolution_type, admin_user, resolution_notes,
    buyer_refund_amount=None, seller_refund_amount=None
) -> DisputeResolution
```

---

## REST API Serializers Available

| Model | Serializer | Fields |
|-------|-----------|--------|
| User | UserSerializer | id, email, username, name, role, is_active |
| User (Detail) | UserDetailSerializer | + failed_login_attempts, locked_until |
| Wallet | WalletSerializer | id, balances[], total_balance_usd |
| WalletBalance | WalletBalanceSerializer | currency, amount, last_updated |
| Deal | DealSerializer | id, seller, currencies, amount, rate, status, receive_amount |
| Transaction | TransactionSerializer | id, type, status, buyer/seller, amounts, currencies |
| Dispute | DisputeSerializer | id, parties, reason, messages[], logs[], resolution |
| Notification | NotificationSerializer | id, type, message, is_read |
| Currency | CurrencySerializer | code, name, symbol |
| ExchangeRate | ExchangeRateSerializer | from/to_currency, rate, change_percent |
| ActivityRecord | ActivityRecordSerializer | user, activity_type, currencies, amount |

---

## Testing Data

### Currencies Seeded (11 total)
```
MYR - Malaysian Ringgit (RM)
USD - US Dollar ($)
EUR - Euro (€)
GBP - British Pound (£)
JPY - Japanese Yen (¥)
AUD - Australian Dollar (A$)
CAD - Canadian Dollar (C$)
CHF - Swiss Franc (CHF)
CNY - Chinese Yuan (¥)
HKD - Hong Kong Dollar (HK$)
NZD - New Zealand Dollar (NZ$)
```

### Exchange Rates Seeded (24 pairs)
```
MYR ↔ USD: 1 MYR = 0.217 USD
MYR ↔ EUR: 1 MYR = 0.198 EUR
MYR ↔ GBP: 1 MYR = 0.171 GBP
... and bidirectional pairs
```

---

## Common Django Commands

### Database Management
```bash
# Show migration status
python manage.py showmigrations

# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Rollback migration
python manage.py migrate <app> <migration_number>

# Reset specific app
python manage.py migrate <app> zero
```

### Data Management
```bash
# Seed currencies and exchange rates
python manage.py populate_currencies

# Create superuser
python manage.py createsuperuser

# Run management shell
python manage.py shell
```

### Verification
```bash
# System check
python manage.py check

# SQL for migrations
python manage.py sqlmigrate <app> <migration>

# Count objects
python manage.py shell
>>> from accounts.models import User
>>> User.objects.count()
```

---

## File Locations

| File | Purpose |
|------|---------|
| `accounts/models.py` | Custom User model |
| `wallets/models.py` | Wallet and balance models |
| `marketplace/models.py` | Deal and Transaction models |
| `disputes/models.py` | Dispute and resolution models |
| `notifications/models.py` | Notification model |
| `core/models.py` | Currency, ExchangeRate, ActivityRecord |
| `marketplace/services.py` | Business logic (PRIMARY) |
| `**/serializers.py` | REST API serializers |
| `**/admin.py` | Django admin configuration |
| `P2PTrade/settings.py` | Project settings |

---

## Configuration Files

### settings.py
```python
# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}

# CORS
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]

# Custom Auth
AUTH_USER_MODEL = 'accounts.User'
```

---

## Error Handling

### Custom Exceptions (core/exceptions.py)
```python
from core.exceptions import (
    InsufficientBalanceError,
    AccountLockedException,
    InvalidTransactionError,
    DealExpiredError,
    DisputeResolutionError
)
```

### Example Usage
```python
try:
    balance.subtract_balance(amount)
except ValueError as e:
    # Handle insufficient balance
    raise InsufficientBalanceError(str(e))
```

---

## Security Features

1. **Account Lock** - Automatic 15-minute lock after 5 failed logins
2. **Atomic DB Transactions** - Multi-step operations are all-or-nothing
3. **Admin-Only Operations** - Dispute resolution requires admin role
4. **Audit Trails** - All dispute actions logged with actor and timestamp
5. **CORS Protection** - Only specified origins can access API
6. **Permission Classes** - REST framework permission system
7. **Read-Only Admin Fields** - Audit logs not editable in admin

---

## Next Steps

### Phase 4: API Implementation
- [ ] Create ViewSets for all models
- [ ] Implement authentication endpoints (register, login)
- [ ] Create deal acceptance endpoint
- [ ] Create payment confirmation endpoints
- [ ] Create dispute resolution endpoints
- [ ] Create wallet deposit/withdrawal endpoints
- [ ] Generate API documentation (drf-spectacular)
- [ ] Add permission classes

### Phase 5: Testing
- [ ] Unit tests for all services
- [ ] Integration tests for API endpoints
- [ ] Load testing
- [ ] Security testing

### Phase 6: Deployment
- [ ] Switch to PostgreSQL for production
- [ ] Configure secure settings for production
- [ ] Set up environment variables
- [ ] Deploy with Gunicorn/uWSGI
- [ ] Set up Celery for background tasks
- [ ] Configure email notifications

---

## Contact & Support

For issues or questions, refer to:
- `DJANGO_DATA_MODELS.md` - Model specifications
- `DJANGO_IMPLEMENTATION_GUIDE.md` - Data flow diagrams
- `IMPLEMENTATION_SUMMARY.md` - Complete implementation details

Generated: May 10, 2026

