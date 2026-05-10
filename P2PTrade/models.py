from django.db import models

# Legacy models have been migrated to separate apps:
# - User model: accounts.models.User
# - Wallet models: wallets.models.Wallet, WalletBalance
# - Deal & Transaction models: marketplace.models.Deal, Transaction
# - Dispute models: disputes.models
# - Notification model: notifications.models.Notification
# - Currency & ExchangeRate: core.models

# This file is kept for backward compatibility but is empty.
