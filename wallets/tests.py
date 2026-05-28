from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from wallets.models import Wallet


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
