"""
Management command to seed the database with realistic dump data.
Usage: python manage.py seed_data
       python manage.py seed_data --clear
"""
from decimal import Decimal
from datetime import timedelta
import random
import string

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from accounts.models import User
from wallets.models import Wallet, WalletBalance
from core.models import Currency, ExchangeRate, ActivityRecord
from marketplace.models import Deal, Transaction


def _make_payment_ref():
    ts = timezone.now().strftime('%Y%m%d%H%M%S')
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f'P2P{ts}{rand}'


def _make_tx_hash():
    return ''.join(random.choices('0123456789abcdef', k=64))


class Command(BaseCommand):
    help = "Seeds the database with realistic test data for the P2P trading platform"

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
            self.stdout.write(self.style.SUCCESS("✓ Data cleared."))

        self.stdout.write("Starting data seeding...")

        # =====================================================================
        # 1. CURRENCIES
        # =====================================================================
        self.stdout.write("  Creating currencies...")
        currencies_data = [
            ("USD", "US Dollar",          "$"),
            ("EUR", "Euro",               "€"),
            ("GBP", "British Pound",      "£"),
            ("JPY", "Japanese Yen",       "¥"),
            ("AUD", "Australian Dollar",  "A$"),
            ("CAD", "Canadian Dollar",    "C$"),
            ("MYR", "Malaysian Ringgit",  "RM"),
        ]
        currencies = {}
        for code, name, symbol in currencies_data:
            currency, _ = Currency.objects.get_or_create(
                code=code,
                defaults={"name": name, "symbol": symbol},
            )
            currencies[code] = currency

        # =====================================================================
        # 2. EXCHANGE RATES
        # =====================================================================
        self.stdout.write("  Creating exchange rates...")
        rates_data = [
            ("USD", "EUR", "0.92"),
            ("USD", "GBP", "0.79"),
            ("USD", "JPY", "149.85"),
            ("USD", "MYR", "4.72"),
            ("USD", "AUD", "1.53"),
            ("USD", "CAD", "1.37"),
            ("EUR", "GBP", "0.86"),
            ("EUR", "MYR", "5.12"),
            ("GBP", "MYR", "5.96"),
        ]
        for f, t, rate in rates_data:
            ExchangeRate.objects.get_or_create(
                from_currency=currencies[f],
                to_currency=currencies[t],
                defaults={"rate": Decimal(rate), "change_percent": Decimal("0.0")},
            )

        # =====================================================================
        # 3. USERS
        # =====================================================================
        self.stdout.write("  Creating users...")
        users_data = [
            # email,                    name,           role,   staff,  superuser, password
            ("admin@p2ptrade.com",  "Admin User",       "admin", True,  True,  "admin123"),
            ("alice@p2ptrade.com",  "Alice Tan",        "user",  False, False, "user1234"),
            ("bob@p2ptrade.com",    "Bob Rahman",       "user",  False, False, "user1234"),
            ("carol@p2ptrade.com",  "Carol Lim",        "user",  False, False, "user1234"),
            ("dave@p2ptrade.com",   "Dave Singh",       "user",  False, False, "user1234"),
        ]
        users = {}
        for email, name, role, staff, superuser, password in users_data:
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={"username": email, "name": name, "role": role},
            )
            user.set_password(password)
            user.name = name
            user.role = role
            user.is_staff = staff
            user.is_superuser = superuser
            user.save()
            users[email] = user

        alice = users["alice@p2ptrade.com"]
        bob   = users["bob@p2ptrade.com"]
        carol = users["carol@p2ptrade.com"]
        dave  = users["dave@p2ptrade.com"]

        # =====================================================================
        # 4. WALLETS  — give everyone generous balances
        # =====================================================================
        self.stdout.write("  Creating wallets & balances...")
        wallet_amounts = {
            "admin@p2ptrade.com": {"USD": 50000, "MYR": 200000, "EUR": 40000, "GBP": 30000},
            "alice@p2ptrade.com": {"USD": 8000,  "MYR": 35000,  "EUR": 5000,  "GBP": 2000, "AUD": 3000},
            "bob@p2ptrade.com":   {"USD": 12000, "MYR": 50000,  "EUR": 8000,  "GBP": 4000, "JPY": 500000},
            "carol@p2ptrade.com": {"USD": 5000,  "MYR": 20000,  "EUR": 3000,  "CAD": 6000},
            "dave@p2ptrade.com":  {"USD": 15000, "MYR": 60000,  "GBP": 10000, "AUD": 8000},
        }
        for email, balances in wallet_amounts.items():
            user   = users[email]
            wallet = user.wallet
            total  = Decimal("0")
            for code, amt in balances.items():
                amount = Decimal(str(amt))
                WalletBalance.objects.update_or_create(
                    wallet=wallet,
                    currency=currencies[code],
                    defaults={"amount": amount},
                )
                total += amount
            wallet.balance_total = total
            wallet.save()

        # =====================================================================
        # 5. DEALS
        # =====================================================================
        self.stdout.write("  Creating deals...")
        now = timezone.now()

        # Helper to create a deal + its "Deal Created" exchange transaction
        def make_deal(seller, from_c, to_c, amount, rate, trend,
                      status, hours_ago=0, hours_duration=48,
                      accepted_hours_ago=None):
            deal = Deal.objects.create(
                seller=seller,
                from_currency=currencies[from_c],
                to_currency=currencies[to_c],
                amount=Decimal(str(amount)),
                rate=Decimal(str(rate)),
                trend=trend,
                status=status,
                created_at=now - timedelta(hours=hours_ago),
                expires_at=now - timedelta(hours=hours_ago) + timedelta(hours=hours_duration),
                accepted_at=(now - timedelta(hours=accepted_hours_ago)
                             if accepted_hours_ago is not None else None),
                balance_reserved=(status == 'active'),
            )
            # "Deal Created" record — type='exchange', seller + user set, no buyer
            Transaction.objects.create(
                seller=seller,
                buyer=None,
                user=seller,
                deal=deal,
                type='exchange',
                from_currency=currencies[from_c],
                to_currency=currencies[to_c],
                amount=Decimal(str(amount)),
                rate=Decimal(str(rate)),
                status='completed',
                payment_reference=f'DEAL{deal.id}',
                completed_at=now - timedelta(hours=hours_ago),
                tx_hash=_make_tx_hash(),
            )
            return deal

        # Active deals (available in the marketplace)
        deal_a1 = make_deal(alice, "USD", "MYR", 1000, "4.72",  "up",   "active", hours_ago=2)
        deal_a2 = make_deal(bob,   "EUR", "MYR", 500,  "5.12",  "up",   "active", hours_ago=5)
        deal_a3 = make_deal(carol, "GBP", "MYR", 300,  "5.96",  "down", "active", hours_ago=1)
        deal_a4 = make_deal(dave,  "USD", "EUR", 2000, "0.92",  "up",   "active", hours_ago=3)
        deal_a5 = make_deal(alice, "AUD", "USD", 1500, "0.65",  "down", "active", hours_ago=8)

        # Accepted/completed deals (will have purchase + sale txns below)
        deal_c1 = make_deal(bob,   "USD", "MYR", 500,  "4.72",  "up",   "accepted",
                            hours_ago=48, accepted_hours_ago=24)
        deal_c2 = make_deal(carol, "EUR", "GBP", 800,  "0.86",  "down", "accepted",
                            hours_ago=72, accepted_hours_ago=48)
        deal_c3 = make_deal(dave,  "GBP", "MYR", 200,  "5.96",  "up",   "accepted",
                            hours_ago=96, accepted_hours_ago=60)
        deal_c4 = make_deal(alice, "USD", "EUR", 1200, "0.92",  "up",   "accepted",
                            hours_ago=120, accepted_hours_ago=90)

        # Expired deals
        make_deal(bob,   "USD", "MYR", 2000, "4.72", "up",   "expired",
                  hours_ago=60, hours_duration=12)
        make_deal(carol, "EUR", "USD", 300,  "1.09", "down", "expired",
                  hours_ago=80, hours_duration=6)

        # Cancelled deals
        make_deal(dave,  "GBP", "USD", 500,  "1.27", "up",   "cancelled", hours_ago=30)
        make_deal(alice, "USD", "MYR", 750,  "4.70", "down", "cancelled", hours_ago=50)

        # =====================================================================
        # 6. TRANSACTIONS — purchase + sale pairs for completed deals
        #    Convention:
        #      purchase txn: buyer=<buyer>,  seller=None   (buyer's record)
        #      sale     txn: buyer=None,     seller=<deal.seller>  (seller's record)
        # =====================================================================
        self.stdout.write("  Creating purchase/sale transactions...")

        def make_p2p_pair(deal, buyer, completed_hours_ago):
            """Create matching purchase (buyer) and sale (seller) transactions."""
            seller          = deal.seller
            from_c          = deal.from_currency   # what seller offers  (e.g. USD)
            to_c            = deal.to_currency      # what buyer pays with (e.g. MYR)
            seller_amount   = deal.amount           # e.g. 500 USD
            buyer_pays      = round(deal.amount / deal.rate, 2)  # e.g. 500/4.72 ≈ 105.93 MYR
            # NOTE: get_receive_amount() = amount / rate = what buyer pays in to_currency
            # Recalculate for clarity:
            # Seller offers `seller_amount` of `from_c`
            # Buyer pays `buyer_pays` of `to_c`  (= seller_amount / rate)
            buyer_pays_dec  = Decimal(str(buyer_pays))
            completed_at    = now - timedelta(hours=completed_hours_ago)

            # ── BUYER record (purchase) ───────────────────────────────────────
            # buyer pays `buyer_pays` MYR, receives `seller_amount` USD
            Transaction.objects.create(
                buyer=buyer,
                seller=None,
                user=None,
                deal=deal,
                type='purchase',
                from_currency=to_c,           # buyer pays in to_currency (MYR)
                to_currency=from_c,           # buyer receives from_currency (USD)
                amount=buyer_pays_dec,        # 105.93 MYR paid
                received_amount=seller_amount,  # 500 USD received
                rate=deal.rate,
                status='completed',
                payment_reference=_make_payment_ref(),
                completed_at=completed_at,
                tx_hash=_make_tx_hash(),
            )

            # ── SELLER record (sale) ─────────────────────────────────────────
            # seller gives `seller_amount` USD, receives `buyer_pays` MYR
            Transaction.objects.create(
                buyer=None,
                seller=seller,
                user=None,
                deal=deal,
                type='sale',
                from_currency=from_c,         # seller gives USD
                to_currency=to_c,             # seller receives MYR
                amount=seller_amount,         # 500 USD given
                received_amount=buyer_pays_dec,  # 105.93 MYR received
                rate=deal.rate,
                status='completed',
                payment_reference=_make_payment_ref(),
                completed_at=completed_at,
                tx_hash=_make_tx_hash(),
            )

        # Pair each accepted deal with a buyer
        make_p2p_pair(deal_c1, buyer=dave,  completed_hours_ago=20)   # bob sold USD→MYR to dave
        make_p2p_pair(deal_c2, buyer=alice, completed_hours_ago=44)   # carol sold EUR→GBP to alice
        make_p2p_pair(deal_c3, buyer=alice, completed_hours_ago=55)   # dave sold GBP→MYR to alice
        make_p2p_pair(deal_c4, buyer=bob,   completed_hours_ago=85)   # alice sold USD→EUR to bob

        # =====================================================================
        # 7. STANDALONE DEPOSITS & WITHDRAWALS
        # =====================================================================
        self.stdout.write("  Creating deposits and withdrawals...")

        deposits = [
            (alice, "USD", "5000",  "1.00", 96),
            (alice, "MYR", "20000", "1.00", 84),
            (bob,   "EUR", "3000",  "1.00", 72),
            (bob,   "MYR", "15000", "1.00", 60),
            (carol, "USD", "2500",  "1.00", 48),
            (carol, "GBP", "1000",  "1.00", 36),
            (dave,  "USD", "8000",  "1.00", 24),
            (dave,  "MYR", "30000", "1.00", 12),
        ]
        for user, code, amount, rate, hours_ago in deposits:
            c = currencies[code]
            Transaction.objects.create(
                user=user,
                buyer=None,
                seller=None,
                type='deposit',
                from_currency=c,
                to_currency=c,
                amount=Decimal(amount),
                received_amount=Decimal(amount),
                rate=Decimal(rate),
                status='completed',
                payment_reference=_make_payment_ref(),
                completed_at=now - timedelta(hours=hours_ago),
                tx_hash=_make_tx_hash(),
            )

        withdrawals = [
            (alice, "USD", "1000",  "1.00", "completed", 80),
            (bob,   "MYR", "5000",  "1.00", "completed", 55),
            (carol, "EUR", "500",   "1.00", "failed",    40),   # failed withdrawal
            (dave,  "USD", "2000",  "1.00", "completed", 10),
            (alice, "MYR", "3000",  "1.00", "pending",    2),   # pending withdrawal
        ]
        for user, code, amount, rate, status, hours_ago in withdrawals:
            c = currencies[code]
            Transaction.objects.create(
                user=user,
                buyer=None,
                seller=None,
                type='withdrawal',
                from_currency=c,
                to_currency=c,
                amount=Decimal(amount),
                received_amount=Decimal(amount) if status == 'completed' else None,
                rate=Decimal(rate),
                status=status,
                payment_reference=_make_payment_ref(),
                completed_at=now - timedelta(hours=hours_ago) if status == 'completed' else None,
                tx_hash=_make_tx_hash(),
            )

        # =====================================================================
        # 8. EDGE-CASE TRANSACTIONS (pending P2P, dispute, failed)
        # =====================================================================
        self.stdout.write("  Creating edge-case transactions...")

        # Pending exchange — buyer accepted but not yet completed
        pending_deal = make_deal(carol, "USD", "MYR", 300, "4.72", "up",
                                 "active", hours_ago=1)
        Transaction.objects.create(
            buyer=dave,
            seller=None,
            deal=pending_deal,
            type='purchase',
            from_currency=currencies["MYR"],
            to_currency=currencies["USD"],
            amount=Decimal("63.56"),      # 300 / 4.72
            received_amount=None,
            rate=Decimal("4.72"),
            status='pending',
            payment_reference=_make_payment_ref(),
        )

        # Dispute-raised exchange
        dispute_deal = make_deal(bob, "EUR", "MYR", 400, "5.12", "up",
                                 "accepted", hours_ago=36, accepted_hours_ago=12)
        Transaction.objects.create(
            buyer=carol,
            seller=None,
            deal=dispute_deal,
            type='purchase',
            from_currency=currencies["MYR"],
            to_currency=currencies["EUR"],
            amount=Decimal("78.13"),      # 400 / 5.12
            received_amount=Decimal("400"),
            rate=Decimal("5.12"),
            status='dispute_raised',
            payment_reference=_make_payment_ref(),
            completed_at=now - timedelta(hours=10),
            tx_hash=_make_tx_hash(),
        )
        Transaction.objects.create(
            buyer=None,
            seller=bob,
            deal=dispute_deal,
            type='sale',
            from_currency=currencies["EUR"],
            to_currency=currencies["MYR"],
            amount=Decimal("400"),
            received_amount=Decimal("78.13"),
            rate=Decimal("5.12"),
            status='dispute_raised',
            payment_reference=_make_payment_ref(),
            completed_at=now - timedelta(hours=10),
            tx_hash=_make_tx_hash(),
        )

        # =====================================================================
        # DONE
        # =====================================================================
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("✓ Database seeding completed successfully!"))
        self.stdout.write("")
        self.stdout.write("  Test accounts:")
        self.stdout.write("    admin@p2ptrade.com  / admin123  (admin)")
        self.stdout.write("    alice@p2ptrade.com  / user1234")
        self.stdout.write("    bob@p2ptrade.com    / user1234")
        self.stdout.write("    carol@p2ptrade.com  / user1234")
        self.stdout.write("    dave@p2ptrade.com   / user1234")
        self.stdout.write("")
        self.stdout.write("  Data summary:")
        self.stdout.write(f"    Currencies:   {Currency.objects.count()}")
        self.stdout.write(f"    Users:        {User.objects.count()}")
        self.stdout.write(f"    Deals:        {Deal.objects.count()}")
        self.stdout.write(f"    Transactions: {Transaction.objects.count()}")