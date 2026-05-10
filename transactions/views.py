from django.shortcuts import render


def index(request):
    """Placeholder index view for transactions.

    This app is a lightweight stub so templates can reverse the
    `transactions:index` namespace while teams implement the real module.
    """
    return render(request, 'transactions/index.html')

