from types import SimpleNamespace
from urllib.parse import quote_plus

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.models import User
from wallets.models import Wallet


def _wallet_or_none(user):
	try:
		return user.wallet
	except Wallet.DoesNotExist:
		return None


def _dashboard_profile(wallet):
	total_balance = wallet.balance_total if wallet else 0
	return SimpleNamespace(
		total_balance_usd=total_balance,
		active_trades=0,
		monthly_profit_usd=0,
	)


def _signup_profile(wallet=None):
	# The old template expected a profile object with starter balances.
	# Keep those values available so the page renders cleanly after migration.
	return SimpleNamespace(
		balance_myr='RM45,000',
		balance_usd='$10,000',
		wallet=wallet,
	)


def login_page(request):
	# Simple login handler: POST will attempt to authenticate by email (used as username)
	if request.method == 'POST':
		email = request.POST.get('email', '').strip()
		password = request.POST.get('password', '')
		user = authenticate(request, username=email, password=password)
		if user is not None:
			login(request, user)
			return redirect(reverse('dashboard'))
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
			return redirect(f"{reverse('login')}?email={quote_plus(email)}")

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
			return redirect(reverse('signup_success'))

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
	wallet = _wallet_or_none(request.user)
	context = {
		'wallet': wallet,
		'profile': _dashboard_profile(wallet),
	}
	return render(request, 'dashboard.html', context)


def logout_view(request):
	logout(request)
	return redirect(reverse('login'))

