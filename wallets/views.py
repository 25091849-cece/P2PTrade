from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Wallet


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
    return {
        **balance,
        'accent_class': meta['accent'],
        'sort_order': meta['order'],
    }


@login_required
def index(request):
    wallet_cards = []

    try:
        wallet = (
            Wallet.objects
            .prefetch_related('balances__currency')
            .get(user=request.user)
        )
    except Wallet.DoesNotExist:
        wallet = None

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

