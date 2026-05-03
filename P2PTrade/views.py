from django.shortcuts import render


def login_page(request):
    return render(request, 'login.html')


def signup_page(request):
    # If the form was submitted, render the success page with the provided name
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        return render(request, 'signup_success.html', {'name': full_name})

    # For GET requests, show the signup form
    return render(request, 'signup.html')
