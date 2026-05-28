"""
Business logic services for marketplace transactions.
Handles complex transaction flows including deal acceptance, payment confirmation, and dispute handling.
"""

from django.db import transaction as db_transaction
from django.utils import timezone
from decimal import Decimal
import uuid
import random
import string

from accounts.models import User
from wallets.models import Wallet, WalletBalance
from core.models import Currency, ActivityRecord
from marketplace.models import Deal, Transaction
from disputes.models import Dispute, DisputeResolution, DisputeActivityLog
from notifications.models import Notification
from core.exceptions import (
    InsufficientBalanceError, InvalidTransactionError, DealExpiredError
)


class DealService:
    """Service for managing currency exchange deals."""

    @staticmethod
    def create_deal(seller: User, from_currency: Currency, to_currency: Currency,
                   amount: Decimal, rate: Decimal, trend: str, duration_hours: int = 48) -> Deal:
        """Create a new deal offering currency exchange."""
        if amount <= 0 or rate <= 0:
            raise InvalidTransactionError("Amount and rate must be positive.")

        # Validate duration
        if duration_hours not in [1, 6, 12, 24, 48]:
            raise InvalidTransactionError("Duration must be 1, 6, 12, 24, or 48 hours")

        deal = Deal.objects.create(
            seller=seller,
            from_currency=from_currency,
            to_currency=to_currency,
            amount=amount,
            rate=rate,
            trend=trend,
            status='active',
            expires_at=timezone.now() + timezone.timedelta(hours=duration_hours)
        )

        # Create offer_created transaction record
        Transaction.objects.create(
            seller=seller,
            user=seller,
            deal=deal,
            type='offer_created',
            from_currency=from_currency,
            to_currency=to_currency,
            amount=amount,
            rate=rate,
            status='pending'
        )

        # Notify seller
        Notification.objects.create(
            user=seller,
            notification_type='deal_accepted',
            message=f'Your deal #{deal.id} has been created and is now active',
            related_id=deal.id
        )

        return deal

    @staticmethod
    @db_transaction.atomic
    def accept_deal(deal: Deal, buyer: User) -> tuple:
        """
        Accept a deal and create transactions for both buyer and seller.
        Returns: (buyer_transaction, seller_transaction)
        """
        # Validate deal is still active
        if deal.is_expired():
            raise DealExpiredError(f"Deal #{deal.id} has expired")

        if deal.status != 'active':
            raise InvalidTransactionError(f"Deal #{deal.id} is not active")

        # Check buyer has sufficient balance
        buyer_wallet = buyer.wallet
        buyer_balance = buyer_wallet.balances.get(currency=deal.to_currency)

        if buyer_balance.amount < deal.get_receive_amount():
            raise InsufficientBalanceError(
                f"Insufficient {deal.to_currency.code} balance. "
                f"Need {deal.get_receive_amount()}, have {buyer_balance.amount}"
            )

        # Generate payment reference
        timestamp = int(timezone.now().timestamp())
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        payment_reference = f"P2P{timestamp}{random_suffix}"

        # Create buyer transaction (purchase)
        buyer_txn = Transaction.objects.create(
            buyer=buyer,
            seller=deal.seller,
            deal=deal,
            type='purchase',
            from_currency=deal.to_currency,
            to_currency=deal.from_currency,
            amount=deal.get_receive_amount(),
            received_amount=deal.amount,
            rate=deal.rate,
            status='awaiting_confirmation',
            payment_reference=payment_reference
        )

        # Create seller transaction (sale)
        seller_txn = Transaction.objects.create(
            buyer=buyer,
            seller=deal.seller,
            deal=deal,
            type='sale',
            from_currency=deal.from_currency,
            to_currency=deal.to_currency,
            amount=deal.amount,
            received_amount=deal.get_receive_amount(),
            rate=deal.rate,
            status='pending',
            payment_reference=payment_reference
        )

        # Update deal status
        deal.status = 'accepted'
        deal.accepted_at = timezone.now()
        deal.save()

        # Send notifications
        Notification.objects.create(
            user=deal.seller,
            notification_type='deal_accepted',
            message=f'Your deal #{deal.id} has been accepted! Payment reference: {payment_reference}',
            related_id=buyer_txn.id
        )

        Notification.objects.create(
            user=buyer,
            notification_type='deal_accepted',
            message=f'You have accepted deal #{deal.id}. Payment reference: {payment_reference}',
            related_id=buyer_txn.id
        )

        return buyer_txn, seller_txn


class PaymentService:
    """Service for managing payment flows and confirmations."""

    @staticmethod
    @db_transaction.atomic
    def confirm_payment(transaction: Transaction, proof_of_payment: str) -> Transaction:
        """
        Buyer uploads proof of payment.
        Changes transaction status from awaiting_confirmation to pending (awaits seller confirmation).
        """
        if transaction.type != 'purchase':
            raise InvalidTransactionError("Only purchase transactions can confirm payment")

        if transaction.status != 'awaiting_confirmation':
            raise InvalidTransactionError(f"Transaction status is {transaction.status}, expected awaiting_confirmation")

        transaction.proof_of_payment = proof_of_payment
        transaction.status = 'pending'
        transaction.save()

        # Notify seller
        Notification.objects.create(
            user=transaction.seller,
            notification_type='payment_confirmed',
            message=f'Payment proof received for transaction #{transaction.id}. Please review.',
            related_id=transaction.id
        )

        return transaction

    @staticmethod
    @db_transaction.atomic
    def confirm_payment_received(buyer_txn: Transaction, seller_user: User) -> tuple:
        """
        Seller confirms payment received. Transfers currencies between wallets.
        Returns: (updated_buyer_txn, updated_seller_txn)
        """
        if buyer_txn.type != 'purchase':
            raise InvalidTransactionError("Expected purchase transaction")

        if buyer_txn.status != 'pending':
            raise InvalidTransactionError(f"Transaction status is {buyer_txn.status}, expected pending")

        # Get linked seller transaction
        seller_txn = Transaction.objects.get(
            deal=buyer_txn.deal,
            type='sale',
            seller=seller_user
        )

        get_seller_wallet = seller_user.wallet
        buyer_wallet = buyer_txn.buyer.wallet

        # Update wallet balances
        buyer_from_balance = buyer_wallet.balances.get(currency=buyer_txn.from_currency)
        buyer_to_balance = buyer_wallet.balances.get(currency=buyer_txn.to_currency)

        seller_from_balance = get_seller_wallet.balances.get(currency=seller_txn.from_currency)
        seller_to_balance = get_seller_wallet.balances.get(currency=seller_txn.to_currency)

        # Deduct from buyer, add to seller (for payment currency)
        buyer_from_balance.subtract_balance(buyer_txn.amount)
        seller_to_balance.add_balance(buyer_txn.amount)

        # Add to buyer, deduct from seller (for received currency)
        buyer_to_balance.add_balance(buyer_txn.received_amount)
        seller_from_balance.subtract_balance(seller_txn.amount)

        # Update transaction statuses
        buyer_txn.status = 'completed'
        buyer_txn.completed_at = timezone.now()
        buyer_txn.save()

        seller_txn.status = 'completed'
        seller_txn.completed_at = timezone.now()
        seller_txn.save()

        # Create activity records
        ActivityRecord.objects.create(
            user=buyer_txn.buyer,
            activity_type='exchange',
            from_currency=buyer_txn.from_currency,
            to_currency=buyer_txn.to_currency,
            amount=buyer_txn.amount
        )

        ActivityRecord.objects.create(
            user=seller_user,
            activity_type='exchange',
            from_currency=seller_txn.from_currency,
            to_currency=seller_txn.to_currency,
            amount=seller_txn.amount
        )

        # Send notifications
        Notification.objects.create(
            user=seller_user,
            notification_type='transaction_completed',
            message=f'Payment confirmed! You received {buyer_txn.amount} {buyer_txn.from_currency.code}',
            related_id=buyer_txn.id
        )

        Notification.objects.create(
            user=buyer_txn.buyer,
            notification_type='transaction_completed',
            message=f'Exchange complete! You received {buyer_txn.received_amount} {buyer_txn.to_currency.code}',
            related_id=buyer_txn.id
        )

        return buyer_txn, seller_txn


class DisputeService:
    """Service for managing dispute resolution."""

    @staticmethod
    @db_transaction.atomic
    def create_dispute(transaction: Transaction, buyer: User, seller: User,
                      reason: str, evidence: str = None) -> Dispute:
        """Create a dispute for a transaction."""
        if len(reason) < 10:
            raise InvalidTransactionError("Dispute reason must be at least 10 characters")

        dispute = Dispute.objects.create(
            transaction=transaction,
            buyer=buyer,
            seller=seller,
            raised_by=buyer if buyer in [transaction.buyer, transaction.seller] else seller,
            from_currency=transaction.from_currency,
            to_currency=transaction.to_currency,
            foreign_amount=transaction.amount,
            myr_amount=transaction.received_amount or transaction.amount,
            reason=reason,
            evidence=evidence,
            status='pending'
        )

        # Mark transaction as disputed
        transaction.status = 'failed'  # or use a 'disputed' status
        transaction.save()

        # Log activity
        DisputeActivityLog.objects.create(
            dispute=dispute,
            actor=dispute.raised_by,
            action=f'Dispute created: {reason}'
        )

        # Notify both parties and admins
        for user in [buyer, seller]:
            Notification.objects.create(
                user=user,
                notification_type='dispute_raised',
                message=f'A dispute has been raised for transaction #{transaction.id}',
                related_id=dispute.id
            )

        return dispute

    @staticmethod
    @db_transaction.atomic
    def resolve_dispute(dispute: Dispute, resolution_type: str,
                       admin_user: User, resolution_notes: str = None,
                       buyer_refund_amount: Decimal = None,
                       seller_refund_amount: Decimal = None) -> DisputeResolution:
        """
        Resolve a dispute with specified resolution type.
        resolution_type: 'release_to_buyer', 'return_to_seller', or 'partial_split'
        """
        if not admin_user.is_admin():
            raise InvalidTransactionError("Only admins can resolve disputes")

        if dispute.status == 'resolved':
            raise InvalidTransactionError("Dispute is already resolved")

        # Update dispute status
        dispute.status = 'resolved'
        dispute.resolved_at = timezone.now()
        dispute.save()

        buyer_wallet = dispute.buyer.wallet
        seller_wallet = dispute.seller.wallet

        buyer_from_balance = buyer_wallet.balances.get(currency=dispute.from_currency)
        buyer_to_balance = buyer_wallet.balances.get(currency=dispute.to_currency)
        seller_from_balance = seller_wallet.balances.get(currency=dispute.from_currency)
        seller_to_balance = seller_wallet.balances.get(currency=dispute.to_currency)

        # Update balances based on resolution type
        if resolution_type == 'release_to_buyer':
            # Buyer gets the foreign currency, seller gets the payment
            buyer_to_balance.add_balance(dispute.foreign_amount)
            seller_to_balance.add_balance(dispute.myr_amount)

        elif resolution_type == 'return_to_seller':
            # Seller gets currency back, buyer loses payment
            seller_from_balance.add_balance(dispute.foreign_amount)
            buyer_from_balance.subtract_balance(dispute.myr_amount)

        elif resolution_type == 'partial_split':
            # Custom split based on refund amounts
            if not buyer_refund_amount or not seller_refund_amount:
                raise InvalidTransactionError("partial_split requires buyer_refund_amount and seller_refund_amount")

            buyer_to_balance.add_balance(buyer_refund_amount)
            seller_to_balance.add_balance(seller_refund_amount)

        # Create resolution record
        resolution = DisputeResolution.objects.create(
            dispute=dispute,
            resolution_type=resolution_type,
            buyer_refund_amount=buyer_refund_amount,
            seller_refund_amount=seller_refund_amount,
            resolution_notes=resolution_notes or f"Dispute resolved with {resolution_type}",
            resolved_by_admin=admin_user
        )

        # Mark transactions as completed
        dispute.transaction.status = 'completed'
        dispute.transaction.completed_at = timezone.now()
        dispute.transaction.save()

        # Log activity
        DisputeActivityLog.objects.create(
            dispute=dispute,
            actor=admin_user,
            action=f'Dispute resolved by admin: {resolution_type}. {resolution_notes}'
        )

        # Send notifications
        for user in [dispute.buyer, dispute.seller]:
            Notification.objects.create(
                user=user,
                notification_type='dispute_resolved',
                message=f'Your dispute #{dispute.id} has been resolved as {resolution_type}',
                related_id=dispute.id
            )

        return resolution

