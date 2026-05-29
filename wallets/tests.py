from django.test import TestCase
from django.urls import reverse
from decimal import Decimal

from accounts.models import User
from core.models import Currency
from marketplace.models import Transaction
from wallets.models import Wallet
from wallets.views import WALLET_VERIFIED_SESSION_KEY


class WalletVerificationLockTests(TestCase):
    def setUp(self):
        self.password = 'correct-password'
        self.user = User.objects.create_user(
            username='wallet-user@example.com',
            email='wallet-user@example.com',
            password=self.password,
        )
        self.wallet = self.user.wallet
        self.url = reverse('wallets:index')

    def test_wallet_lock_persists_after_new_login_session(self):
        self.client.login(username=self.user.email, password=self.password)

        for _ in range(4):
            self.client.post(self.url, {'password': 'wrong-password'})

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.verification_failed_attempts, 4)
        self.assertIsNotNone(self.wallet.verification_locked_until)

        self.client.logout()
        self.client.login(username=self.user.email, password=self.password)

        response = self.client.get(self.url)

        self.assertContains(response, 'Account temporarily locked')
        self.assertContains(response, 'Please try again')


class WalletInitialBalanceTests(TestCase):
    def setUp(self):
        self.myr = Currency.objects.create(
            code='MYR',
            name='Malaysian Ringgit',
            symbol='RM',
        )
        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
        )
        self.eur = Currency.objects.create(
            code='EUR',
            name='Euro',
            symbol='EUR',
        )

    def test_new_user_gets_configured_initial_balances(self):
        user = User.objects.create_user(
            username='initial-balance@example.com',
            email='initial-balance@example.com',
            password='password',
        )

        balances = {
            balance.currency.code: balance.amount
            for balance in user.wallet.balances.all()
        }
        self.assertEqual(balances['MYR'], Decimal('45000.00'))
        self.assertEqual(balances['USD'], Decimal('10000.00'))
        self.assertEqual(balances['EUR'], Decimal('0.00'))


class DepositCompletionTests(TestCase):
    def setUp(self):
        self.currency = Currency.objects.create(
            code='MYR',
            name='Malaysian Ringgit',
            symbol='RM',
        )
        self.user = User.objects.create_user(
            username='deposit-user@example.com',
            email='deposit-user@example.com',
            password='password',
        )
        self.miki = User.objects.create_user(
            username='miki@example.com',
            email='miki@example.com',
            password='password',
            name='MIKI',
        )

    def _create_pending_deposit(self, user=None):
        user = user or self.user
        return Transaction.objects.create(
            user=user,
            type='deposit',
            from_currency=self.currency,
            to_currency=self.currency,
            amount=Decimal('125.00'),
            received_amount=Decimal('125.00'),
            rate=Decimal('1.00'),
            status='pending',
            payment_reference='TOP123',
            proof_of_payment=f'wallet_deposits/user_{self.user.id}/TOP123_proof.png',
        )

    def test_completing_deposit_credits_requesting_user_wallet(self):
        txn = self._create_pending_deposit()

        txn.status = 'completed'
        txn.save()

        applicant_balance = self.user.wallet.balances.get(currency=self.currency)
        self.assertEqual(applicant_balance.amount, Decimal('45125.00'))
        txn.refresh_from_db()
        self.assertEqual(txn.user, self.user)

    def test_completed_deposit_is_not_credited_twice(self):
        txn = self._create_pending_deposit()

        txn.status = 'completed'
        txn.save()
        txn.save()

        applicant_balance = self.user.wallet.balances.get(currency=self.currency)
        self.assertEqual(applicant_balance.amount, Decimal('45125.00'))

    def test_completed_deposit_uses_proof_applicant_if_admin_changes_user(self):
        txn = self._create_pending_deposit()

        txn.user = self.miki
        txn.status = 'completed'
        txn.save()

        applicant_balance = self.user.wallet.balances.get(currency=self.currency)
        miki_balance = self.miki.wallet.balances.get(currency=self.currency)
        self.assertEqual(applicant_balance.amount, Decimal('45125.00'))
        self.assertEqual(miki_balance.amount, Decimal('45000.00'))
        txn.refresh_from_db()
        self.assertEqual(txn.user, self.user)


class WithdrawBalanceTests(TestCase):
    def setUp(self):
        self.currency = Currency.objects.create(
            code='MYR',
            name='Malaysian Ringgit',
            symbol='RM',
        )
        self.user = User.objects.create_user(
            username='withdraw-user@example.com',
            email='withdraw-user@example.com',
            password='password',
        )
        self.client.login(username=self.user.email, password='password')
        session = self.client.session
        session[WALLET_VERIFIED_SESSION_KEY] = True
        session.save()
        self.url = reverse('wallets:withdraw')

    def test_withdraw_page_shows_selected_currency_balance(self):
        balance = self.user.wallet.balances.get(currency=self.currency)
        balance.amount = Decimal('25.50')
        balance.save()

        response = self.client.get(self.url)

        self.assertEqual(response.context['selected_balance']['display'], '25.50')
        self.assertContains(response, 'Available balance: 25.50 MYR')

    def test_withdraw_rejects_amount_above_available_balance(self):
        balance = self.user.wallet.balances.get(currency=self.currency)
        balance.amount = Decimal('25.50')
        balance.save()

        response = self.client.post(self.url, {
            'currency': 'MYR',
            'amount': '26.00',
        })

        self.assertContains(response, 'Insufficient Balance')
        self.assertContains(
            response,
            'Insufficient balance. You have 25.50 MYR available to withdraw.',
        )

    def test_valid_withdraw_shows_confirmation_on_same_page(self):
        balance = self.user.wallet.balances.get(currency=self.currency)
        balance.amount = Decimal('25.50')
        balance.save()

        response = self.client.post(self.url, {
            'currency': 'MYR',
            'amount': '20.00',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_withdraw_confirmation'])
        self.assertContains(response, 'Withdraw Confirmation')
        self.assertContains(response, 'Proceed with Wallet Withdrawal')
        self.assertContains(response, 'Proceed Withdraw')

    def test_confirm_withdraw_creates_pending_withdrawal(self):
        balance = self.user.wallet.balances.get(currency=self.currency)
        balance.amount = Decimal('25.50')
        balance.save()

        response = self.client.post(self.url, {
            'confirm_withdrawal': '1',
            'confirm_request': 'on',
            'currency': 'MYR',
            'amount': '20.00',
            'bank_account': '1234567890',
            'owner_name': 'Test Owner',
        })

        self.assertRedirects(response, reverse('transactions:index'))
        transaction = Transaction.objects.get(type='withdrawal')
        self.assertEqual(transaction.user, self.user)
        self.assertEqual(transaction.amount, Decimal('20.00'))
        self.assertEqual(transaction.status, 'pending')
        self.assertIn('1234567890', transaction.proof_of_payment)
        self.assertIn('Test Owner', transaction.proof_of_payment)

    def test_completing_withdrawal_debits_requesting_user_wallet(self):
        balance = self.user.wallet.balances.get(currency=self.currency)
        balance.amount = Decimal('25.50')
        balance.save()
        transaction = Transaction.objects.create(
            user=self.user,
            type='withdrawal',
            from_currency=self.currency,
            to_currency=self.currency,
            amount=Decimal('20.00'),
            received_amount=Decimal('20.00'),
            rate=Decimal('1.00'),
            status='pending',
            proof_of_payment='Bank Account: 1234567890\nOwner Name: Test Owner',
        )

        transaction.status = 'completed'
        transaction.save()

        balance.refresh_from_db()
        self.assertEqual(balance.amount, Decimal('5.50'))
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, 'completed')
        self.assertIsNotNone(transaction.completed_at)

    def test_completed_withdrawal_is_not_debited_twice(self):
        balance = self.user.wallet.balances.get(currency=self.currency)
        balance.amount = Decimal('25.50')
        balance.save()
        transaction = Transaction.objects.create(
            user=self.user,
            type='withdrawal',
            from_currency=self.currency,
            to_currency=self.currency,
            amount=Decimal('20.00'),
            received_amount=Decimal('20.00'),
            rate=Decimal('1.00'),
            status='pending',
            proof_of_payment='Bank Account: 1234567890\nOwner Name: Test Owner',
        )

        transaction.status = 'completed'
        transaction.save()
        transaction.save()

        balance.refresh_from_db()
        self.assertEqual(balance.amount, Decimal('5.50'))
