import json
from types import SimpleNamespace
from urllib.parse import quote_plus
from decimal import Decimal
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q, Sum

from accounts.context_processors import is_admin_user as check_is_admin_user
from accounts.models import User
from wallets.models import Wallet, WalletBalance
from marketplace.models import Deal, Transaction
from core.models import ExchangeRate
from disputes.models import Dispute


def _wallet_or_none(user):
	try:
		return user.wallet
	except Wallet.DoesNotExist:
		return None


def _dashboard_profile(user, wallet):
	total_balance = wallet.balance_total if wallet else 0

	# Count active deals (trades)
	active_trades = Deal.objects.filter(
		seller=user,
		status='active'
	).count()

	# Calculate monthly profit from completed transactions
	month_ago = timezone.now() - timedelta(days=30)
	monthly_profit = Transaction.objects.filter(
		Q(seller=user) | Q(buyer=user),
		status='completed',
		completed_at__gte=month_ago
	).aggregate(total=Sum('received_amount'))['total'] or Decimal(0)

	return SimpleNamespace(
		total_balance_usd=total_balance,
		active_trades=active_trades,
		monthly_profit_usd=monthly_profit,
	)


def _signup_profile(wallet=None):
	# The old template expected a profile object with starter balances.
	# Keep those values available so the page renders cleanly after migration.
	return SimpleNamespace(
		balance_myr='RM45,000',
		balance_usd='$10,000',
		wallet=wallet,
	)


def _is_admin_user(user):
	return check_is_admin_user(user)


def _admin_dashboard_context():
	"""Context for the admin dashboard cards + chart."""
	total_users = User.objects.count()
	active_users = User.objects.filter(is_active=True).count()
	total_transactions = Transaction.objects.count()
	pending_disputes = Dispute.objects.filter(status='pending').count()
	resolved_disputes = Dispute.objects.filter(status='resolved').count()
	active_deals = Deal.objects.filter(status='active').count()
	today = timezone.now().date()

	volume = (
		Transaction.objects
		.filter(status='completed')
		.values('to_currency__code')
		.annotate(total=Sum('received_amount'))
		.order_by('-total')[:11]
	)
	volume_data = [
		{'code': r['to_currency__code'], 'volume': float(r['total'] or 0)}
		for r in volume
	]
	if not volume_data:
		volume_data = [
			{'code': c, 'volume': v} for c, v in [
				('USD', 680000), ('EUR', 640000), ('GBP', 625000),
				('JPY', 490000), ('AUD', 480000), ('CAD', 475000),
				('CHF', 460000), ('CNY', 455000), ('HKD', 450000),
				('NZD', 445000), ('MYR', 440000),
			]
		]

	return {
		'stats': {
			'total_users': total_users,
			'active_users': active_users,
			'total_transactions': total_transactions,
			'pending_disputes': pending_disputes,
			'resolved_disputes': resolved_disputes,
			'active_deals': active_deals,
			'new_users_today': User.objects.filter(created_at__date=today).count(),
			'new_transactions_today': Transaction.objects.filter(created_at__date=today).count(),
		},
		'volume_data': json.dumps(volume_data),
	}


def login_page(request):
	# Simple login handler: POST will attempt to authenticate by email (used as username)
	if request.method == 'POST':
		email = request.POST.get('email', '').strip()
		password = request.POST.get('password', '')
		user = authenticate(request, username=email, password=password)
		if user is not None:
			login(request, user)
			return redirect(reverse('accounts:dashboard'))
		return render(request, 'account/login.html', {'error': 'Invalid credentials', 'email': email})

	prefill_email = request.GET.get('email', '').strip()
	return render(request, 'account/login.html', {'email': prefill_email})


def signup_page(request):
	# Handle form POST: create a Django User, log them in, then redirect (PRG)
	if request.method == 'POST':
		full_name = request.POST.get('full_name', '').strip()
		email = request.POST.get('email', '').strip()
		password = request.POST.get('password', '')

		# Basic validation
		error = None
		if not full_name:
			error = 'Please enter your full name.'
		elif not email:
			error = 'Please enter your email address.'
		elif not password or len(password) < 6:
			error = 'Password must be at least 6 characters.'
		elif User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
			messages.info(request, 'This email is already registered. Please login.')
			return redirect(f"{reverse('accounts:login')}?email={quote_plus(email)}")

		if error:
			# Re-render form with error and previously entered values
			return render(request, 'account/signup.html', {
				'error': error,
				'full_name': full_name,
				'email': email,
			})

		# Create the user
		parts = full_name.split()
		first_name = parts[0] if parts else ''
		last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''

		user = User.objects.create_user(
			username=email,
			email=email,
			password=password,
			first_name=first_name,
			last_name=last_name,
			name=full_name
		)

		# Log the user in
		user = authenticate(request, username=email, password=password)
		if user is not None:
			login(request, user)
			# Wallet is created automatically via signals
			return redirect(reverse('accounts:signup_success'))

		# Fallback (shouldn't normally happen)
		return render(request, 'account/signup.html', {'error': 'Unable to log you in after signup.'})

	# GET: show signup form
	return render(request, 'account/signup.html')


@login_required(login_url='login')
def signup_success(request):
	wallet = _wallet_or_none(request.user)
	context = {
		'profile': _signup_profile(wallet),
		'wallet': wallet,
	}
	return render(request, 'account/signup_success.html', context)


@login_required(login_url='login')
def dashboard_page(request):
	is_admin_user = _is_admin_user(request.user)

	# Admin: redesigned Figma dashboard (stats + chart + Platform Health)
	if is_admin_user:
		return render(request, 'admin_dashboard.html', _admin_dashboard_context())

	# Regular user: keep the original dashboard untouched
	wallet = _wallet_or_none(request.user)
	try:
		exchange_rates = ExchangeRate.objects.select_related(
			'from_currency', 'to_currency'
		).filter(
			from_currency__code='USD'
		).order_by('to_currency__code')[:6]
	except:
		exchange_rates = []

	recent_transactions = Transaction.objects.filter(
		Q(buyer=request.user) | Q(seller=request.user) | Q(user=request.user)
	).select_related(
		'from_currency', 'to_currency', 'buyer', 'seller', 'user'
	).order_by('-created_at')[:5]

	recent_activity = []
	for txn in recent_transactions:
		activity = SimpleNamespace(
			type=txn.get_type_display() if hasattr(txn, 'get_type_display') else txn.type.upper(),
			description=f"{txn.from_currency.code} → {txn.to_currency.code}",
			amount=f"{txn.amount}",
			timestamp=txn.created_at,
			status=txn.status,
		)
		recent_activity.append(activity)

	return render(request, 'dashboard.html', {
		'wallet': wallet,
		'profile': _dashboard_profile(request.user, wallet),
		'exchange_rates': exchange_rates,
		'recent_activity': recent_activity,
		'is_admin_user': False,
	})


def logout_view(request):
	logout(request)
	return redirect(reverse('accounts:login'))

@login_required(login_url='login')
def manage_user(request):
	"""Admin-only user management page (search + USD/EUR balances + role)."""
	if not _is_admin_user(request.user):
		return redirect(reverse('accounts:dashboard'))

	search = request.GET.get('q', '').strip()
	qs = User.objects.all().order_by('-created_at')
	if search:
		qs = qs.filter(
			Q(email__icontains=search) | Q(name__icontains=search) | Q(username__icontains=search)
		)

	users = []
	for u in qs:
		u.usd_balance = WalletBalance.objects.filter(
			wallet__user=u, currency__code='USD',
		).values_list('amount', flat=True).first() or 0
		u.eur_balance = WalletBalance.objects.filter(
			wallet__user=u, currency__code='EUR',
		).values_list('amount', flat=True).first() or 0
		users.append(u)

	return render(request, 'admin/management/manage_user.html', {
		'users': users,
		'stats': {
			'total_users': User.objects.count(),
			'active_users': User.objects.filter(is_active=True).count(),
			'admins': User.objects.filter(role='admin').count(),
		},
		'search': search,
	})
