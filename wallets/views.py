from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import Wallet


MAX_WALLET_ATTEMPTS = 4
WALLET_LOCK_MINUTES = 15
WALLET_ATTEMPTS_SESSION_KEY = 'wallet_failed_attempts'
WALLET_LOCKED_UNTIL_SESSION_KEY = 'wallet_locked_until'
WALLET_VERIFIED_SESSION_KEY = 'wallet_verified'

CURRENCY_META = {
    'MYR': {'accent': 'wallet-accent-myr', 'order': 1},
    'USD': {'accent': 'wallet-accent-usd', 'order': 2},
    'EUR': {'accent': 'wallet-accent-eur', 'order': 3},
    'JPY': {'accent': 'wallet-accent-jpy', 'order': 4},
    'GBP': {'accent': 'wallet-accent-gbp', 'order': 5},
    'AUD': {'accent': 'wallet-accent-aud', 'order': 6},
    'CAD': {'accent': 'wallet-accent-cad', 'order': 7},
    'CHF': {'accent': 'wallet-accent-chf', 'order': 8},
    'CNY': {'accent': 'wallet-accent-cny', 'order': 9},
    'HKD': {'accent': 'wallet-accent-hkd', 'order': 10},
    'NZD': {'accent': 'wallet-accent-nzd', 'order': 11},
}

DEPOSIT_CURRENCIES = tuple(CURRENCY_META.keys())

FALLBACK_BALANCES = [
    {'currency_name': 'Malaysian Ringgit', 'currency_code': 'MYR', 'amount': Decimal('0.00')},
    {'currency_name': 'US Dollar', 'currency_code': 'USD', 'amount': Decimal('9000.00')},
    {'currency_name': 'Euro', 'currency_code': 'EUR', 'amount': Decimal('8500.00')},
    {'currency_name': 'Japanese Yen', 'currency_code': 'JPY', 'amount': Decimal('1200000.00')},
    {'currency_name': 'British Pound', 'currency_code': 'GBP', 'amount': Decimal('7500.00')},
]


def _decorate_balance(balance):
    code = balance['currency_code']
    meta = CURRENCY_META.get(code, {'accent': 'wallet-accent-default', 'order': 99})
    amount = balance['amount']
    return {
        **balance,
        'display_amount': f'{amount:,.2f}',
        'accent_class': meta['accent'],
        'sort_order': meta['order'],
    }


def _clear_wallet_verification_failures(request, wallet=None):
    request.session.pop(WALLET_ATTEMPTS_SESSION_KEY, None)
    request.session.pop(WALLET_LOCKED_UNTIL_SESSION_KEY, None)

    if wallet and (wallet.verification_failed_attempts or wallet.verification_locked_until):
        wallet.verification_failed_attempts = 0
        wallet.verification_locked_until = None
        wallet.save(update_fields=[
            'verification_failed_attempts',
            'verification_locked_until',
            'updated_at',
        ])


def _clear_wallet_verification(request):
    request.session.pop(WALLET_VERIFIED_SESSION_KEY, None)


def _get_wallet_for_user(user):
    try:
        return Wallet.objects.prefetch_related('balances__currency').get(user=user)
    except Wallet.DoesNotExist:
        return None


def _get_wallet_lock_remaining_seconds(request, wallet=None):
    if wallet and wallet.verification_locked_until:
        remaining_seconds = int((wallet.verification_locked_until - timezone.now()).total_seconds())
        if remaining_seconds <= 0:
            _clear_wallet_verification_failures(request, wallet)
            return 0

        return remaining_seconds

    locked_until = request.session.get(WALLET_LOCKED_UNTIL_SESSION_KEY)
    if not locked_until:
        return 0

    remaining_seconds = int(locked_until - timezone.now().timestamp())
    if remaining_seconds <= 0:
        _clear_wallet_verification_failures(request, wallet)
        return 0

    return remaining_seconds


def _render_wallet_verification(request, wallet=None, **context):
    remaining_seconds = _get_wallet_lock_remaining_seconds(request, wallet)
    locked_minutes = max(1, (remaining_seconds + 59) // 60) if remaining_seconds else 0

    return render(request, 'wallets/verify.html', {
        'is_locked': remaining_seconds > 0,
        'locked_minutes': locked_minutes,
        **context,
    })


@login_required
def index(request):
    wallet = _get_wallet_for_user(request.user)

    if (
        request.method == 'GET'
        and request.session.get(WALLET_VERIFIED_SESSION_KEY)
        and _is_entering_wallet_from_other_module(request)
    ):
        _clear_wallet_verification(request)

    if not request.session.get(WALLET_VERIFIED_SESSION_KEY):
        if _get_wallet_lock_remaining_seconds(request, wallet):
            return _render_wallet_verification(request, wallet=wallet)

        if request.method == 'POST':
            password = request.POST.get('password', '')

            if request.user.check_password(password):
                _clear_wallet_verification_failures(request, wallet)
                request.session[WALLET_VERIFIED_SESSION_KEY] = True
                return redirect('wallets:index')

            if wallet:
                wallet.verification_failed_attempts += 1
                failed_attempts = wallet.verification_failed_attempts
                update_fields = ['verification_failed_attempts', 'updated_at']
            else:
                failed_attempts = request.session.get(WALLET_ATTEMPTS_SESSION_KEY, 0) + 1
                request.session[WALLET_ATTEMPTS_SESSION_KEY] = failed_attempts

            if failed_attempts >= MAX_WALLET_ATTEMPTS:
                locked_until = timezone.now() + timezone.timedelta(minutes=WALLET_LOCK_MINUTES)

                if wallet:
                    wallet.verification_locked_until = locked_until
                    update_fields.append('verification_locked_until')
                else:
                    request.session[WALLET_LOCKED_UNTIL_SESSION_KEY] = locked_until.timestamp()

            if wallet:
                wallet.save(update_fields=update_fields)

            if failed_attempts >= MAX_WALLET_ATTEMPTS:
                return _render_wallet_verification(request, wallet=wallet)

            attempts_remaining = MAX_WALLET_ATTEMPTS - failed_attempts
            return _render_wallet_verification(
                request,
                wallet=wallet,
                attempts_remaining=attempts_remaining,
            )

        return _render_wallet_verification(request, wallet=wallet)

    wallet_cards = []

    if wallet:
        wallet_cards = [
            _decorate_balance({
                'currency_name': balance.currency.name,
                'currency_code': balance.currency.code,
                'amount': balance.amount,
            })
            for balance in wallet.balances.all()
        ]

    if not wallet_cards:
        wallet_cards = [_decorate_balance(balance) for balance in FALLBACK_BALANCES]

    wallet_cards.sort(key=lambda card: card['sort_order'])

    return render(request, 'wallets/index.html', {
        'wallet_cards': wallet_cards,
    })


@login_required
def deposit(request):
    if not request.session.get(WALLET_VERIFIED_SESSION_KEY):
        return redirect('wallets:index')

    selected_currency = request.GET.get('currency', 'MYR').upper()
    if selected_currency not in DEPOSIT_CURRENCIES:
        selected_currency = 'MYR'

    return render(request, 'wallets/deposit.html', {
        'currencies': DEPOSIT_CURRENCIES,
        'selected_currency': selected_currency,
    })


def _is_entering_wallet_from_other_module(request):
    referer = request.META.get('HTTP_REFERER', '')
    if not referer:
        return False

    host = request.get_host()
    wallet_path = request.path
    return host in referer and wallet_path not in referer


@login_required
def clear_verification(request):
    if request.method == 'POST':
        _clear_wallet_verification(request)
        return HttpResponse(status=204)

    return HttpResponse(status=405)

