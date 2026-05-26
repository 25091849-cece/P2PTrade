"""
Management command to seed the database with realistic dump data.
Usage: python manage.py seed_data --clear
"""

from decimal import Decimal
from datetime import timedelta
import random

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from accounts.models import User
from wallets.models import Wallet, WalletBalance
from core.models import Currency, ExchangeRate, ActivityRecord
from marketplace.models import Deal, Transaction


class Command(BaseCommand):
    help = "Seeds the database with realistic dump data for P2P trading platform"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing data before seeding",
        )

    @transaction.atomic
    def handle(self, *args, **options):

        if options["clear"]:
            self.stdout.write("Clearing existing data...")

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

        # =========================
        # 1. CURRENCIES
        # =========================
        self.stdout.write("Creating currencies...")

        currencies_data = [
            ("USD", "US Dollar", "$"),
            ("EUR", "Euro", "€"),
            ("GBP", "British Pound", "£"),
            ("JPY", "Japanese Yen", "¥"),
            ("AUD", "Australian Dollar", "A$"),
            ("CAD", "Canadian Dollar", "C$"),
            ("MYR", "Malaysian Ringgit", "RM"),
        ]

        currencies = {}
        for code, name, symbol in currencies_data:
            currency, _ = Currency.objects.get_or_create(
                code=code,
                defaults={"name": name, "symbol": symbol},
            )
            currencies[code] = currency

        # =========================
        # 2. EXCHANGE RATES
        # =========================
        self.stdout.write("Creating exchange rates...")

        exchange_rate_data = [
            ("USD", "EUR", Decimal("0.92")),
            ("USD", "GBP", Decimal("0.79")),
            ("USD", "JPY", Decimal("149.85")),
            ("EUR", "GBP", Decimal("0.86")),
            ("USD", "MYR", Decimal("4.85")),
        ]

        for f, t, rate in exchange_rate_data:
            ExchangeRate.objects.get_or_create(
                from_currency=currencies[f],
                to_currency=currencies[t],
                defaults={"rate": rate, "change_percent": Decimal("0.0")},
            )

        # =========================
        # 3. USERS
        # =========================
        self.stdout.write("Creating users...")

        users_data = [
            ("admin@p2ptrade.com", "Admin User", "admin", True, True, "admin123"),
            ("user@p2ptrade.com", "Demo User", "user", False, False, "user1234"),
            ("trader@p2ptrade.com", "Trader User", "user", False, False, "trader1234"),
        ]

        users = {}

        for email, name, role, staff, superuser, password in users_data:

            user, _ = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": email,
                    "name": name,
                    "role": role,
                    "is_staff": staff,
                    "is_superuser": superuser,
                },
            )

            user.set_password(password)
            user.is_staff = staff
            user.is_superuser = superuser
            user.role = role
            user.save()

            users[email] = user

        # =========================
        # 4. WALLETS
        # =========================
        self.stdout.write("Creating wallets...")

        for user in users.values():

            wallet = user.wallet

            total = Decimal("0")

            for code, currency in currencies.items():
                amount = Decimal("10000")

                WalletBalance.objects.update_or_create(
                    wallet=wallet,
                    currency=currency,
                    defaults={"amount": amount},
                )

                total += amount

            wallet.balance_total = total
            wallet.save()

        # =========================
        # 5. DEALS
        # =========================
        self.stdout.write("Creating deals...")

        Deal.objects.get_or_create(
            seller=users["user@p2ptrade.com"],
            from_currency=currencies["USD"],
            to_currency=currencies["EUR"],
            amount=Decimal("1500"),
            defaults={
                "rate": Decimal("0.92"),
                "trend": "up",
                "status": "active",
                "expires_at": timezone.now() + timedelta(hours=48),
            },
        )

        Deal.objects.get_or_create(
            seller=users["trader@p2ptrade.com"],
            from_currency=currencies["EUR"],
            to_currency=currencies["GBP"],
            amount=Decimal("800"),
            defaults={
                "rate": Decimal("0.86"),
                "trend": "down",
                "status": "active",
                "expires_at": timezone.now() + timedelta(hours=48),
            },
        )

        # =========================
        # 6. TRANSACTIONS
        # =========================
        self.stdout.write("Creating transactions...")

        now = timezone.now()

        transactions = [
            {
                "buyer": users["user@p2ptrade.com"],
                "seller": users["admin@p2ptrade.com"],
                "from_currency": "USD",
                "to_currency": "EUR",
                "amount": "1200",
                "rate": "0.92",
                "status": "completed",
                "hours": 3,
            },
            {
                "buyer": users["user@p2ptrade.com"],
                "seller": None,
                "user": users["user@p2ptrade.com"],
                "from_currency": "USD",
                "to_currency": "USD",
                "amount": "5000",
                "rate": "1.00",
                "status": "completed",
                "hours": 24,
            },
            {
                "buyer": users["trader@p2ptrade.com"],
                "seller": users["user@p2ptrade.com"],
                "from_currency": "EUR",
                "to_currency": "GBP",
                "amount": "500",
                "rate": "0.86",
                "status": "pending",
                "hours": 0,
            },
        ]

        for tx in transactions:

            hours = tx.pop("hours")

            Transaction.objects.create(
                buyer=tx.get("buyer"),
                seller=tx.get("seller"),
                user=tx.get("user"),
                from_currency=currencies[tx["from_currency"]],
                to_currency=currencies[tx["to_currency"]],
                amount=Decimal(tx["amount"]),
                rate=Decimal(tx["rate"]),
                status=tx["status"],
                created_at=now - timedelta(hours=hours),
                completed_at=(
                    now - timedelta(hours=hours)
                    if tx["status"] == "completed"
                    else None
                ),
                tx_hash="".join(
                    random.choices("0123456789abcdef", k=64)
                ),
            )

        # =========================
        # DONE
        # =========================
        self.stdout.write(self.style.SUCCESS("✓ Database seeding completed successfully!"))