from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from urllib.parse import quote_plus
from .models import UserProfile


def login_page(request):
    # Simple login handler: POST will attempt to authenticate by email (used as username)
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect(reverse('dashboard'))
        return render(request, 'login.html', {'error': 'Invalid credentials', 'email': email})

    prefill_email = request.GET.get('email', '').strip()
    return render(request, 'login.html', {'email': prefill_email})


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
            return render(request, 'signup.html', {
                'error': error,
                'full_name': full_name,
                'email': email,
            })

        # Create the user
        parts = full_name.split()
        first_name = parts[0] if parts else ''
        last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''

        user = User.objects.create_user(username=email, email=email, password=password,
                                        first_name=first_name, last_name=last_name)

        # Log the user in
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            # Create UserProfile with starting balances
            UserProfile.objects.create(user=user)
            return redirect(reverse('signup_success'))

        # Fallback (shouldn't normally happen)
        return render(request, 'signup.html', {'error': 'Unable to log you in after signup.'})

    # GET: show signup form
    return render(request, 'signup.html')


@login_required(login_url='login')
def signup_success(request):
    # Render a simple signup success page. The user is already logged in.
    return render(request, 'signup_success.html')


@login_required(login_url='login')
def dashboard_page(request):
    # Get the user's profile
    profile = UserProfile.objects.get(user=request.user)

    context = {
        'profile': profile,
    }
    return render(request, 'dashboard.html', context)


def logout_view(request):
    logout(request)
    return redirect(reverse('login'))

