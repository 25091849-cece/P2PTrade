import json
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import quote_plus

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.context_processors import is_admin_user as check_is_admin_user
from accounts.models import User
from core.models import ActivityRecord, ExchangeRate
from disputes.models import Dispute
from marketplace.models import Deal, Transaction
from wallets.models import Wallet, WalletBalance


def _wallet_or_none(user):
    try:
        return user.wallet
    except Wallet.DoesNotExist:
        return None


def _dashboard_profile(user, wallet):
    total_balance = wallet.balance_total if wallet else 0

    # Count active deals (trades)
    active_trades = Deal.objects.filter(seller=user, status="active").count()

    # Calculate monthly profit from completed transactions
    month_ago = timezone.now() - timedelta(days=30)
    monthly_profit = Transaction.objects.filter(
        Q(seller=user) | Q(buyer=user), status="completed", completed_at__gte=month_ago
    ).aggregate(total=Sum("received_amount"))["total"] or Decimal(0)

    return SimpleNamespace(
        total_balance_usd=total_balance,
        active_trades=active_trades,
        monthly_profit_usd=monthly_profit,
    )


def _signup_profile(wallet=None):
    # The old template expected a profile object with starter balances.
    # Keep those values available so the page renders cleanly after migration.
    return SimpleNamespace(
        balance_myr="RM45,000",
        balance_usd="$10,000",
        wallet=wallet,
    )


def _is_admin_user(user):
    return check_is_admin_user(user)


def _admin_dashboard_context():
    """Context for the admin dashboard cards + chart."""
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    total_transactions = Transaction.objects.count()
    pending_disputes = Dispute.objects.filter(status="pending").count()
    resolved_disputes = Dispute.objects.filter(status="resolved").count()
    active_deals = Deal.objects.filter(status="active").count()
    today = timezone.now().date()

    volume = (
        Transaction.objects.filter(status="completed")
        .values("to_currency__code")
        .annotate(total=Sum("received_amount"))
        .order_by("-total")[:11]
    )
    volume_data = [
        {"code": r["to_currency__code"], "volume": float(r["total"] or 0)}
        for r in volume
    ]
    if not volume_data:
        volume_data = [
            {"code": c, "volume": v}
            for c, v in [
                ("USD", 680000),
                ("EUR", 640000),
                ("GBP", 625000),
                ("JPY", 490000),
                ("AUD", 480000),
                ("CAD", 475000),
                ("CHF", 460000),
                ("CNY", 455000),
                ("HKD", 450000),
                ("NZD", 445000),
                ("MYR", 440000),
            ]
        ]

    return {
        "stats": {
            "total_users": total_users,
            "active_users": active_users,
            "total_transactions": total_transactions,
            "pending_disputes": pending_disputes,
            "resolved_disputes": resolved_disputes,
            "active_deals": active_deals,
            "new_users_today": User.objects.filter(created_at__date=today).count(),
            "new_transactions_today": Transaction.objects.filter(
                created_at__date=today
            ).count(),
        },
        "volume_data": json.dumps(volume_data),
    }


def login_page(request):
    # Simple login handler: POST will attempt to authenticate by email (used as username)
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect(reverse("accounts:dashboard"))
        return render(
            request,
            "account/login.html",
            {"error": "Invalid credentials", "email": email},
        )

    prefill_email = request.GET.get("email", "").strip()
    return render(request, "account/login.html", {"email": prefill_email})


def signup_page(request):
    # Handle form POST: create a Django User, log them in, then redirect (PRG)
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        # Basic validation
        error = None
        if not full_name:
            error = "Please enter your full name."
        elif not email:
            error = "Please enter your email address."
        elif not password or len(password) < 6:
            error = "Password must be at least 6 characters."
        elif (
            User.objects.filter(username__iexact=email).exists()
            or User.objects.filter(email__iexact=email).exists()
        ):
            messages.info(request, "This email is already registered. Please login.")
            return redirect(f"{reverse('accounts:login')}?email={quote_plus(email)}")

        if error:
            # Re-render form with error and previously entered values
            return render(
                request,
                "account/signup.html",
                {
                    "error": error,
                    "full_name": full_name,
                    "email": email,
                },
            )

        # Create the user
        parts = full_name.split()
        first_name = parts[0] if parts else ""
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            name=full_name,
        )

        # Log the user in
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            # Wallet is created automatically via signals
            return redirect(reverse("accounts:signup_success"))

        # Fallback (shouldn't normally happen)
        return render(
            request,
            "account/signup.html",
            {"error": "Unable to log you in after signup."},
        )

    # GET: show signup form
    return render(request, "account/signup.html")


@login_required(login_url="login")
def signup_success(request):
    wallet = _wallet_or_none(request.user)
    context = {
        "profile": _signup_profile(wallet),
        "wallet": wallet,
    }
    return render(request, "account/signup_success.html", context)

"""
Replace the dashboard_page function in accounts/views.py with this version.
All other functions in that file remain unchanged.
"""

@login_required(login_url="login")
def dashboard_page(request):
    is_admin_user = _is_admin_user(request.user)

    if is_admin_user:
        return render(request, "admin_dashboard.html", _admin_dashboard_context())

    user   = request.user
    wallet = _wallet_or_none(user)
    now    = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # ── 1. Wallet balances (all currencies) ──────────────────────────────────
    wallet_balances = []
    if wallet:
        for wb in (
            wallet.balances
            .select_related("currency")
            .filter(amount__gt=0)
            .order_by("-amount")
        ):
            wallet_balances.append({
                "code":   wb.currency.code,
                "name":   wb.currency.name,
                "symbol": wb.currency.symbol,
                "amount": wb.amount,
            })

    # ── 2. Monthly profit — received amounts grouped by currency ─────────────
    completed_this_month = Transaction.objects.filter(
        Q(buyer=user) | Q(seller=user),
        status="completed",
        completed_at__gte=month_start,
        type__in=["purchase", "sale"],
    ).select_related("to_currency")

    profit_by_currency = {}
    for txn in completed_this_month:
        code = txn.to_currency.code
        profit_by_currency[code] = profit_by_currency.get(
            code, Decimal("0")
        ) + (txn.received_amount or Decimal("0"))

    monthly_profits = [
        {"code": code, "amount": amount}
        for code, amount in sorted(profit_by_currency.items(), key=lambda x: -x[1])
    ]

    # ── 3. Active trades (deals user is selling, still active) ───────────────
    active_deals_qs = (
        Deal.objects.filter(seller=user, status="active")
        .select_related("from_currency", "to_currency")
        .order_by("-created_at")[:5]
    )
    active_trades_count = Deal.objects.filter(seller=user, status="active").count()

    # ── 4. Transactions this month ────────────────────────────────────────────
    txns_this_month = Transaction.objects.filter(
        Q(buyer=user) | Q(seller=user) | Q(user=user),
        created_at__gte=month_start,
    ).count()

    # ── 5. Marketplace — available deals (not from this user) ────────────────
    marketplace_deals = (
        Deal.objects.filter(status="active")
        .exclude(seller=user)
        .select_related("seller", "from_currency", "to_currency")
        .order_by("-created_at")[:6]
    )

    # ── 6. Recent activity (last 8 transactions) ──────────────────────────────
    recent_txns = (
        Transaction.objects.filter(
            Q(buyer=user) | Q(seller=user) | Q(user=user)
        )
        .select_related("from_currency", "to_currency", "buyer", "seller", "user")
        .order_by("-created_at")[:8]
    )

    recent_activity = []
    for txn in recent_txns:
        # Determine display label
        label = txn.get_type_display()

        # Counterparty name for P2P types
        counterparty = ""
        if txn.type == "purchase" and txn.deal:
            counterparty = txn.deal.seller.name or txn.deal.seller.email
        elif txn.type == "sale" and txn.deal:
            sibling = txn.deal.transactions.filter(
                type="purchase"
            ).select_related("buyer").first()
            if sibling and sibling.buyer:
                counterparty = sibling.buyer.name or sibling.buyer.email

        # Amount string — show what the user received where possible
        if txn.received_amount:
            amount_str = f"+{txn.received_amount:,.2f} {txn.to_currency.code}"
        else:
            amount_str = f"{txn.amount:,.2f} {txn.from_currency.code}"

        recent_activity.append({
            "type":         label,
            "pair":         f"{txn.from_currency.code} → {txn.to_currency.code}",
            "amount":       amount_str,
            "counterparty": counterparty,
            "status":       txn.status,
            "timestamp":    txn.created_at,
        })

    # ── 7. Exchange rates ─────────────────────────────────────────────────────
    try:
        exchange_rates = (
            ExchangeRate.objects.select_related("from_currency", "to_currency")
            .filter(from_currency__code="USD")
            .order_by("to_currency__code")[:6]
        )
    except Exception:
        exchange_rates = []

    # ── 8. Profile summary object ─────────────────────────────────────────────
    total_balance = wallet.balance_total if wallet else Decimal("0")
    monthly_profit_total = sum(p["amount"] for p in monthly_profits)

    profile = SimpleNamespace(
        total_balance_usd=total_balance,
        active_trades=active_trades_count,
        monthly_profit_usd=monthly_profit_total,
    )

    return render(request, "dashboard.html", {
        "wallet":             wallet,
        "profile":            profile,
        "wallet_balances":    wallet_balances,
        "monthly_profits":    monthly_profits,
        "active_deals":       active_deals_qs,
        "active_trades_count": active_trades_count,
        "marketplace_deals":  marketplace_deals,
        "transactions_this_month": txns_this_month,
        "recent_activity":    recent_activity,
        "exchange_rates":     exchange_rates,
        "total_balance_change_display": f"${total_balance:,.2f}",
        "is_admin_user":      False,
    })


def logout_view(request):
    logout(request)
    return redirect(reverse("accounts:login"))


@login_required(login_url="login")
def manage_user(request):
    """Admin-only user management page (search + USD/EUR balances + role)."""
    if not _is_admin_user(request.user):
        return redirect(reverse("accounts:dashboard"))

    search = request.GET.get("q", "").strip()
    qs = User.objects.all().order_by("-created_at")
    if search:
        qs = qs.filter(
            Q(email__icontains=search)
            | Q(name__icontains=search)
            | Q(username__icontains=search)
        )

    users = []
    for u in qs:
        u.usd_balance = (
            WalletBalance.objects.filter(
                wallet__user=u,
                currency__code="USD",
            )
            .values_list("amount", flat=True)
            .first()
            or 0
        )
        u.eur_balance = (
            WalletBalance.objects.filter(
                wallet__user=u,
                currency__code="EUR",
            )
            .values_list("amount", flat=True)
            .first()
            or 0
        )
        users.append(u)

    return render(
        request,
        "admin/management/manage_user.html",
        {
            "users": users,
            "stats": {
                "total_users": User.objects.count(),
                "active_users": User.objects.filter(is_active=True).count(),
                "admins": User.objects.filter(role="admin").count(),
            },
            "search": search,
        },
    )
