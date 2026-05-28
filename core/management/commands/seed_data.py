"""
Management command to seed the database with realistic dump data.
Usage: python manage.py seed_data
"""

from decimal import Decimal
from datetime import timedelta, datetime
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction

from accounts.models import User
from wallets.models import Wallet, WalletBalance
from core.models import Currency, ExchangeRate, ActivityRecord
from marketplace.models import Deal, Transaction


class Command(BaseCommand):
    help = 'Seeds the database with realistic dump data for P2P trading platform'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before seeding',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write("Clearing existing data...")
            # Delete in the correct order to respect foreign key constraints
            Transaction.objects.all().delete()
            Deal.objects.all().delete()
            ExchangeRate.objects.all().delete()
            ActivityRecord.objects.all().delete()
            WalletBalance.objects.all().delete()
            Wallet.objects.all().delete()
            User.objects.all().delete()
            Currency.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Data cleared successfully!"))

        self.stdout.write("Starting data seeding...")

        # 1. Create Currencies
        self.stdout.write("Creating currencies...")
        currencies_data = [
            ('USD', 'US Dollar', '$'),
            ('EUR', 'Euro', '€'),
            ('GBP', 'British Pound', '£'),
            ('JPY', 'Japanese Yen', '¥'),
            ('AUD', 'Australian Dollar', 'A$'),
            ('CAD', 'Canadian Dollar', 'C$'),
            ('CHF', 'Swiss Franc', 'CHF'),
            ('CNY', 'Chinese Yuan', '¥'),
            ('HKD', 'Hong Kong Dollar', 'HK$'),
            ('NZD', 'New Zealand Dollar', 'NZ$'),
            ('MYR', 'Malaysian Ringgit', 'RM'),
        ]

        currencies = {}
        for code, name, symbol in currencies_data:
            currency, created = Currency.objects.get_or_create(
                code=code,
                defaults={'name': name, 'symbol': symbol}
            )
            currencies[code] = currency
            if created:
                self.stdout.write(f"  ✓ Created currency: {code}")

        # 2. Create Exchange Rates (USD-based)
        self.stdout.write("Creating exchange rates...")
        exchange_rate_data = [
            ('USD', 'EUR', Decimal('0.92'), Decimal('1.2')),
            ('USD', 'GBP', Decimal('0.79'), Decimal('-0.5')),
            ('USD', 'JPY', Decimal('149.85'), Decimal('0.6')),
            ('USD', 'AUD', Decimal('1.52'), Decimal('2.1')),
            ('USD', 'CAD', Decimal('1.36'), Decimal('0.8')),
            ('USD', 'CHF', Decimal('0.88'), Decimal('-0.2')),
            ('EUR', 'GBP', Decimal('0.86'), Decimal('-0.3')),
            ('EUR', 'JPY', Decimal('162.90'), Decimal('0.5')),
            ('GBP', 'JPY', Decimal('189.32'), Decimal('0.9')),
            ('USD', 'MYR', Decimal('4.85'), Decimal('1.5')),
        ]

        for from_code, to_code, rate, change_percent in exchange_rate_data:
            exchange_rate, created = ExchangeRate.objects.get_or_create(
                from_currency=currencies[from_code],
                to_currency=currencies[to_code],
                defaults={
                    'rate': rate,
                    'change_percent': change_percent,
                }
            )
            if created:
                self.stdout.write(f"  ✓ Created exchange rate: {from_code}->{to_code}")

        # 3. Create Test Users
        self.stdout.write("Creating test users...")
        test_users_data = [
            {
                'username': 'test@gmail.com',
                'email': 'test@gmail.com',
                'password': 'test1234',
                'first_name': 'Test',
                'last_name': 'User',
                'name': 'Test User',
            },
            {
                'username': 'merchant@gmail.com',
                'email': 'merchant@gmail.com',
                'password': 'merchant1234',
                'first_name': 'John',
                'last_name': 'Merchant',
                'name': 'John Merchant',
            },
            {
                'username': 'trader@gmail.com',
                'email': 'trader@gmail.com',
                'password': 'trader1234',
                'first_name': 'Jane',
                'last_name': 'Trader',
                'name': 'Jane Trader',
            },
        ]

        users = {}
        for user_data in test_users_data:
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults={
                    'email': user_data['email'],
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                    'name': user_data['name'],
                }
            )
            if created:
                user.set_password(user_data['password'])
                user.save()
                self.stdout.write(f"  ✓ Created user: {user_data['name']}")
            users[user_data['email']] = user

        # 4. Create Wallets and Balances
        self.stdout.write("Creating wallets and balances...")
        initial_balances = {
            'USD': Decimal('10000.00'),
            'EUR': Decimal('8000.00'),
            'GBP': Decimal('6000.00'),
            'JPY': Decimal('1500000.00'),
            'MYR': Decimal('50000.00'),
        }

        for user_email, user in users.items():
            wallet = user.wallet  # Wallet created via signal

            # Update wallet balances with initial amounts
            total_balance = Decimal(0)
            for currency_code, amount in initial_balances.items():
                wallet_balance, created = WalletBalance.objects.get_or_create(
                    wallet=wallet,
                    currency=currencies[currency_code],
                    defaults={'amount': amount}
                )
                if not created:
                    # Update amount if balance already exists
                    wallet_balance.amount = amount
                    wallet_balance.save()
                total_balance += amount

            # Update wallet total
            wallet.balance_total = total_balance
            wallet.save()

            self.stdout.write(f"  ✓ Created wallet for: {user.name}")

        # 5. Create Deals (Active Marketplace Listings)
        self.stdout.write("Creating marketplace deals...")
        main_user = users['test@gmail.com']
        merchant_user = users['merchant@gmail.com']

        deals_data = [
            {
                'seller': main_user,
                'from_currency': 'USD',
                'to_currency': 'EUR',
                'amount': Decimal('1500.00'),
                'rate': Decimal('0.92'),
                'trend': 'up',
                'status': 'active',
            },
            {
                'seller': merchant_user,
                'from_currency': 'USD',
                'to_currency': 'GBP',
                'amount': Decimal('2000.00'),
                'rate': Decimal('0.79'),
                'trend': 'down',
                'status': 'active',
            },
            {
                'seller': users['trader@gmail.com'],
                'from_currency': 'EUR',
                'to_currency': 'GBP',
                'amount': Decimal('500.00'),
                'rate': Decimal('0.86'),
                'trend': 'up',
                'status': 'active',
            },
            {
                'seller': main_user,
                'from_currency': 'GBP',
                'to_currency': 'JPY',
                'amount': Decimal('800.00'),
                'rate': Decimal('189.32'),
                'trend': 'up',
                'status': 'active',
            },
        ]

        for deal_data in deals_data:
            now = timezone.now()
            Deal.objects.get_or_create(
                seller=deal_data['seller'],
                from_currency=currencies[deal_data['from_currency']],
                to_currency=currencies[deal_data['to_currency']],
                amount=deal_data['amount'],
                defaults={
                    'rate': deal_data['rate'],
                    'trend': deal_data['trend'],
                    'status': deal_data['status'],
                    'created_at': now,
                    'expires_at': now + timedelta(hours=48),
                }
            )
            self.stdout.write(f"  ✓ Created deal: {deal_data['from_currency']}->{deal_data['to_currency']}")

        # 6. Create Transactions
        self.stdout.write("Creating transactions...")
        transactions_data = [
            {
                'buyer': main_user,
                'seller': merchant_user,
                'from_currency': 'USD',
                'to_currency': 'EUR',
                'amount': Decimal('1200.00'),
                'received_amount': Decimal('1104.00'),
                'rate': Decimal('0.92'),
                'type': 'purchase',
                'status': 'completed',
                'days_ago': 0,
            },
            {
                'buyer': main_user,
                'seller': None,
                'user': main_user,
                'from_currency': 'USD',
                'to_currency': 'USD',
                'amount': Decimal('5000.00'),
                'received_amount': Decimal('5000.00'),
                'rate': Decimal('1.00'),
                'type': 'deposit',
                'status': 'completed',
                'days_ago': 1,
            },
            {
                'buyer': main_user,
                'seller': users['trader@gmail.com'],
                'from_currency': 'EUR',
                'to_currency': 'GBP',
                'amount': Decimal('500.00'),
                'received_amount': Decimal('430.00'),
                'rate': Decimal('0.86'),
                'type': 'exchange',
                'status': 'completed',
                'days_ago': 2,
            },
        ]

        for txn_data in transactions_data:
            days_ago = txn_data.pop('days_ago')
            created_at = timezone.now() - timedelta(days=days_ago)
            completed_at = created_at + timedelta(hours=2) if txn_data['status'] == 'completed' else None

            Transaction.objects.get_or_create(
                buyer=txn_data.pop('buyer'),
                seller=txn_data.pop('seller'),
                user=txn_data.pop('user', None),
                from_currency=currencies[txn_data.pop('from_currency')],
                to_currency=currencies[txn_data.pop('to_currency')],
                amount=txn_data.pop('amount'),
                defaults={
                    'received_amount': txn_data['received_amount'],
                    'rate': txn_data['rate'],
                    'type': txn_data['type'],
                    'status': txn_data['status'],
                    'created_at': created_at,
                    'completed_at': completed_at,
                    'timestamp': created_at,
                    **txn_data
                }
            )
            self.stdout.write(f"  ✓ Created transaction: {txn_data['type']}")

        # 7. Create Activity Records
        self.stdout.write("Creating activity records...")
        for user_email, user in users.items():
            ActivityRecord.objects.get_or_create(
                user=user,
                activity_type='exchange',
                from_currency=currencies['USD'],
                to_currency=currencies['EUR'],
                amount=Decimal('100.00'),
                defaults={
                    'timestamp': timezone.now() - timedelta(hours=2),
                }
            )
            self.stdout.write(f"  ✓ Created activity record for: {user.name}")

        self.stdout.write(self.style.SUCCESS('✓ Data seeding completed successfully!'))
        self.stdout.write("\nTest users created:")
        for user_email, user in users.items():
            self.stdout.write(f"  Email: {user_email}, Password: test1234/merchant1234/trader1234")

