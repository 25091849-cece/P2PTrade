import re

from django.db import transaction as db_transaction
from django.utils import timezone

from accounts.models import User
from marketplace.models import Transaction

from .models import Wallet, WalletBalance, get_initial_balance


WALLET_CREDIT_PREFIX = 'wallet-credit:'
WALLET_DEBIT_PREFIX = 'wallet-debit:'
PROOF_USER_RE = re.compile(r'(?:^|/)wallet_deposits/user_(\d+)(?:/|$)')


def _wallet_marker(prefix, transaction_id):
    return f'{prefix}{transaction_id}'


def _get_or_create_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(
        user=user,
        defaults={'id': f'user-{user.id}'},
    )
    return wallet


def _get_or_create_balance(user, currency):
    wallet = _get_or_create_wallet(user)
    balance, _ = WalletBalance.objects.get_or_create(
        wallet=wallet,
        currency=currency,
        defaults={'amount': get_initial_balance(currency.code)},
    )
    return balance


def _get_proof_applicant(transaction):
    proof = transaction.proof_of_payment or ''
    match = PROOF_USER_RE.search(proof.replace('\\', '/'))
    if not match:
        return None

    try:
        return User.objects.get(pk=match.group(1))
    except User.DoesNotExist:
        return None


def _get_deposit_applicant(transaction):
    return _get_proof_applicant(transaction) or transaction.user


@db_transaction.atomic
def credit_completed_deposit(transaction):
    """Add a completed deposit to the original applicant's wallet once."""
    if transaction.type != 'deposit' or transaction.status != 'completed':
        return False

    locked = Transaction.objects.select_for_update().get(pk=transaction.pk)
    marker = _wallet_marker(WALLET_CREDIT_PREFIX, locked.pk)
    if locked.tx_hash == marker:
        return False

    applicant = _get_deposit_applicant(locked)
    if applicant is None:
        return False

    amount = locked.received_amount or locked.amount
    balance = _get_or_create_balance(applicant, locked.to_currency)
    balance.add_balance(amount)

    updates = {
        'user': applicant,
        'tx_hash': marker,
    }
    if locked.completed_at is None:
        updates['completed_at'] = timezone.now()

    Transaction.objects.filter(pk=locked.pk).update(**updates)
    transaction.user = applicant
    transaction.tx_hash = marker
    if 'completed_at' in updates:
        transaction.completed_at = updates['completed_at']
    return True


@db_transaction.atomic
def debit_completed_withdrawal(transaction):
    """Subtract a completed withdrawal from the applicant's wallet once."""
    if transaction.type != 'withdrawal' or transaction.status != 'completed':
        return False

    locked = Transaction.objects.select_for_update().get(pk=transaction.pk)
    marker = _wallet_marker(WALLET_DEBIT_PREFIX, locked.pk)
    if locked.tx_hash == marker:
        return False

    if locked.user is None:
        return False

    balance = _get_or_create_balance(locked.user, locked.from_currency)
    balance = WalletBalance.objects.select_for_update().get(pk=balance.pk)
    balance.subtract_balance(locked.amount)

    updates = {'tx_hash': marker}
    if locked.completed_at is None:
        updates['completed_at'] = timezone.now()

    Transaction.objects.filter(pk=locked.pk).update(**updates)
    transaction.tx_hash = marker
    if 'completed_at' in updates:
        transaction.completed_at = updates['completed_at']
    return True
