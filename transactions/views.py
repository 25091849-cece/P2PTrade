from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from marketplace.models import Transaction


@login_required
def index(request):
    user = request.user
    transactions = (
        Transaction.objects
        .filter(Q(buyer=user) | Q(seller=user) | Q(user=user))
        .select_related('from_currency', 'to_currency', 'buyer', 'seller')
        .order_by('-created_at')
    )
    return render(request, 'transactions/index.html', {'transactions': transactions})


def admin_index(request):
    transactions = Transaction.objects.select_related(
        'buyer', 'seller', 'user', 'from_currency', 'to_currency'
    ).order_by('-created_at')
    return render(request, 'admin/transactions/admin_transaction.html', {'transactions': transactions})


