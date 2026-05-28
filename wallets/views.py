import random
import string
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils.text import get_valid_filename
from django.utils import timezone

from core.models import Currency
from marketplace.models import Transaction
from .models import Wallet, get_initial_balance


MAX_WALLET_ATTEMPTS = 4
WALLET_LOCK_MINUTES = 15
WALLET_ATTEMPTS_SESSION_KEY = 'wallet_failed_attempts'
WALLET_LOCKED_UNTIL_SESSION_KEY = 'wallet_locked_until'
WALLET_VERIFIED_SESSION_KEY = 'wallet_verified'
DEPOSIT_TOP_UP_SESSION_KEY = 'wallet_deposit_top_up'

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
WITHDRAW_CURRENCIES = DEPOSIT_CURRENCIES

CURRENCY_SYMBOLS = {
    'MYR': 'RM',
    'USD': '$',
    'EUR': '€',
    'JPY': '¥',
    'GBP': '£',
    'AUD': 'A$',
    'CAD': 'C$',
    'CHF': 'CHF',
    'CNY': '¥',
    'HKD': 'HK$',
    'NZD': 'NZ$',
}

CURRENCY_NAMES = {
    'MYR': 'Malaysian Ringgit',
    'USD': 'US Dollar',
    'EUR': 'Euro',
    'JPY': 'Japanese Yen',
    'GBP': 'British Pound',
    'AUD': 'Australian Dollar',
    'CAD': 'Canadian Dollar',
    'CHF': 'Swiss Franc',
    'CNY': 'Chinese Yuan',
    'HKD': 'Hong Kong Dollar',
    'NZD': 'New Zealand Dollar',
}

DEPOSIT_BANK_ACCOUNTS = {
    'MYR': {'bank': 'Maybank', 'account_name': 'P2PTrade Malaysia Sdn Bhd', 'account_number': '5142 8891 0092'},
    'USD': {'bank': 'Citi Bank', 'account_name': 'P2PTrade Global Ltd', 'account_number': '8821 0045 7710'},
    'EUR': {'bank': 'HSBC Europe', 'account_name': 'P2PTrade Global Ltd', 'account_number': 'EU91 4000 6622 1098'},
    'JPY': {'bank': 'MUFG Bank', 'account_name': 'P2PTrade Global Ltd', 'account_number': '0198 5520 7311'},
    'GBP': {'bank': 'Barclays', 'account_name': 'P2PTrade Global Ltd', 'account_number': 'GB24 BARC 2048 8822 7100'},
    'AUD': {'bank': 'ANZ Bank', 'account_name': 'P2PTrade Global Ltd', 'account_number': '082-991 4410 8221'},
    'CAD': {'bank': 'RBC Bank', 'account_name': 'P2PTrade Global Ltd', 'account_number': '003 711 8802551'},
    'CHF': {'bank': 'UBS Switzerland', 'account_name': 'P2PTrade Global Ltd', 'account_number': 'CH93 0076 2011 6238'},
    'CNY': {'bank': 'Bank of China', 'account_name': 'P2PTrade Global Ltd', 'account_number': '6222 8891 4400 7188'},
    'HKD': {'bank': 'HSBC Hong Kong', 'account_name': 'P2PTrade Global Ltd', 'account_number': '128-882110-838'},
    'NZD': {'bank': 'ANZ New Zealand', 'account_name': 'P2PTrade Global Ltd', 'account_number': '01-1822-0118481-00'},
}

FALLBACK_BALANCES = [
    {'currency_name': 'Malaysian Ringgit', 'currency_code': 'MYR', 'amount': get_initial_balance('MYR')},
    {'currency_name': 'US Dollar', 'currency_code': 'USD', 'amount': get_initial_balance('USD')},
    {'currency_name': 'Euro', 'currency_code': 'EUR', 'amount': get_initial_balance('EUR')},
    {'currency_name': 'Japanese Yen', 'currency_code': 'JPY', 'amount': get_initial_balance('JPY')},
    {'currency_name': 'British Pound', 'currency_code': 'GBP', 'amount': get_initial_balance('GBP')},
    {'currency_name': 'Australian Dollar', 'currency_code': 'AUD', 'amount': get_initial_balance('AUD')},
    {'currency_name': 'Canadian Dollar', 'currency_code': 'CAD', 'amount': get_initial_balance('CAD')},
    {'currency_name': 'Swiss Franc', 'currency_code': 'CHF', 'amount': get_initial_balance('CHF')},
    {'currency_name': 'Chinese Yuan', 'currency_code': 'CNY', 'amount': get_initial_balance('CNY')},
    {'currency_name': 'Hong Kong Dollar', 'currency_code': 'HKD', 'amount': get_initial_balance('HKD')},
    {'currency_name': 'New Zealand Dollar', 'currency_code': 'NZD', 'amount': get_initial_balance('NZD')},
]


def _decorate_balance(balance):
    code = balance['currency_code']
    meta = CURRENCY_META.get(code, {'accent': 'wallet-accent-default', 'order': 99})
    amount = balance['amount']
    return {
        **balance,
        'display_amount': f'{amount:,.2f}',
        'currency_symbol': CURRENCY_SYMBOLS.get(code, code),
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


def _format_deposit_amount(amount, currency):
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    if symbol in {'$', 'RM', '€', '£', '¥', 'A$', 'C$', 'HK$', 'NZ$', 'CHF'}:
        return f'{symbol} {amount:,.2f}'
    return f'{amount:,.2f} {symbol}'


def _generate_top_up_reference():
    timestamp = timezone.now().strftime('%y%m%d%H%M%S')
    suffix = ''.join(random.choices(string.digits, k=4))
    return f'TOP{timestamp}{suffix}'


def _build_top_up_context(top_up, **extra):
    amount = Decimal(top_up['amount'])
    currency = top_up['currency']
    return {
        'amount': amount,
        'currency': currency,
        'amount_display': _format_deposit_amount(amount, currency),
        'receive_display': f'{amount:,.2f} {currency}',
        'reference': top_up['reference'],
        'bank_account': DEPOSIT_BANK_ACCOUNTS[currency],
        **extra,
    }


def _get_or_create_deposit_currency(code):
    return Currency.objects.get_or_create(
        code=code,
        defaults={
            'name': CURRENCY_NAMES.get(code, code),
            'symbol': CURRENCY_SYMBOLS.get(code, code),
        },
    )[0]


def _get_withdraw_balance_options(user):
    wallet = _get_wallet_for_user(user)
    amounts = {code: Decimal('0.00') for code in WITHDRAW_CURRENCIES}

    if wallet:
        for balance in wallet.balances.all():
            code = balance.currency.code
            if code in amounts:
                amounts[code] = balance.amount

    return {
        code: {
            'amount': str(amounts[code].quantize(Decimal('0.01'))),
            'display': f'{amounts[code]:,.2f}',
        }
        for code in WITHDRAW_CURRENCIES
    }


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

    amount_value = ''
    error_message = ''

    if request.method == 'POST':
        selected_currency = request.POST.get('currency', 'MYR').upper()
        amount_value = request.POST.get('amount', '').strip()

        if selected_currency not in DEPOSIT_CURRENCIES:
            error_message = 'Please choose a supported deposit currency.'
            selected_currency = 'MYR'
        else:
            try:
                amount = Decimal(amount_value).quantize(Decimal('0.01'))
                if amount <= 0:
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                error_message = 'Please enter a valid deposit amount.'
            else:
                request.session[DEPOSIT_TOP_UP_SESSION_KEY] = {
                    'currency': selected_currency,
                    'amount': str(amount),
                    'reference': _generate_top_up_reference(),
                }
                return redirect('wallets:top_up')

    return render(request, 'wallets/deposit.html', {
        'currencies': DEPOSIT_CURRENCIES,
        'selected_currency': selected_currency,
        'amount_value': amount_value,
        'error_message': error_message,
    })


@login_required
def withdraw(request):
    if not request.session.get(WALLET_VERIFIED_SESSION_KEY):
        return redirect('wallets:index')

    withdraw_balances = _get_withdraw_balance_options(request.user)
    selected_currency = request.GET.get('currency', 'MYR').upper()
    if selected_currency not in WITHDRAW_CURRENCIES:
        selected_currency = 'MYR'

    amount_value = ''
    error_message = ''
    error_title = ''
    show_withdraw_confirmation = False
    confirmation_amount = None
    bank_account_value = ''
    owner_name_value = ''

    if request.method == 'POST':
        selected_currency = request.POST.get('currency', 'MYR').upper()
        amount_value = request.POST.get('amount', '').strip()
        is_confirmation_step = request.POST.get('confirm_withdrawal') == '1'
        bank_account_value = request.POST.get('bank_account', '').strip()
        owner_name_value = request.POST.get('owner_name', '').strip()
        is_confirmation = is_confirmation_step and request.POST.get('confirm_request') == 'on'

        if selected_currency not in WITHDRAW_CURRENCIES:
            error_message = 'Please choose a supported withdrawal currency.'
            selected_currency = 'MYR'
        else:
            try:
                amount = Decimal(amount_value).quantize(Decimal('0.01'))
                if amount <= 0:
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                error_message = 'Please enter a valid withdrawal amount.'
            else:
                available_balance = Decimal(withdraw_balances[selected_currency]['amount'])
                if amount > available_balance:
                    error_title = 'Insufficient Balance'
                    error_message = (
                        f'Insufficient balance. You have {available_balance:,.2f} '
                        f'{selected_currency} available to withdraw.'
                    )
                elif is_confirmation_step:
                    show_withdraw_confirmation = True
                    confirmation_amount = amount

                    if not bank_account_value:
                        error_message = 'Please enter the bank account.'
                    elif not owner_name_value:
                        error_message = 'Please enter the owner name.'
                    elif not is_confirmation:
                        error_message = 'Please confirm that you want to submit this withdrawal request.'
                    else:
                        currency = _get_or_create_deposit_currency(selected_currency)
                        Transaction.objects.create(
                            user=request.user,
                            type='withdrawal',
                            from_currency=currency,
                            to_currency=currency,
                            amount=amount,
                            received_amount=amount,
                            rate=Decimal('1.00'),
                            status='pending',
                            proof_of_payment=f'Bank Account: {bank_account_value}\nOwner Name: {owner_name_value}',
                        )
                        return redirect('transactions:index')
                else:
                    show_withdraw_confirmation = True
                    confirmation_amount = amount

    return render(request, 'wallets/withdraw.html', {
        'currencies': WITHDRAW_CURRENCIES,
        'selected_currency': selected_currency,
        'amount_value': amount_value,
        'error_message': error_message,
        'error_title': error_title,
        'show_withdraw_confirmation': show_withdraw_confirmation,
        'confirmation_amount': confirmation_amount,
        'bank_account_value': bank_account_value,
        'owner_name_value': owner_name_value,
        'selected_balance': withdraw_balances[selected_currency],
        'withdraw_balances': withdraw_balances,
    })


@login_required
def top_up(request):
    if not request.session.get(WALLET_VERIFIED_SESSION_KEY):
        return redirect('wallets:index')

    top_up_details = request.session.get(DEPOSIT_TOP_UP_SESSION_KEY)
    if not top_up_details:
        return redirect('wallets:deposit')

    if request.method == 'POST':
        proof = request.FILES.get('payment_proof')
        confirmed = request.POST.get('confirm_transfer') == 'on'

        if not proof:
            return render(request, 'wallets/top_up.html', _build_top_up_context(
                top_up_details,
                error_message='Please upload your payment proof.',
            ))

        if not confirmed:
            return render(request, 'wallets/top_up.html', _build_top_up_context(
                top_up_details,
                error_message='Please confirm that you have completed the transfer.',
            ))

        safe_name = get_valid_filename(proof.name)
        amount = Decimal(top_up_details['amount']).quantize(Decimal('0.01'))
        currency = _get_or_create_deposit_currency(top_up_details['currency'])
        proof_path = default_storage.save(
            f'wallet_deposits/user_{request.user.id}/{top_up_details["reference"]}_{safe_name}',
            proof,
        )
        Transaction.objects.create(
            user=request.user,
            type='deposit',
            from_currency=currency,
            to_currency=currency,
            amount=amount,
            received_amount=amount,
            rate=Decimal('1.00'),
            status='pending',
            payment_reference=top_up_details['reference'],
            proof_of_payment=proof_path,
        )
        request.session.pop(DEPOSIT_TOP_UP_SESSION_KEY, None)

        return redirect('transactions:index')

    return render(request, 'wallets/top_up.html', _build_top_up_context(top_up_details))


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

