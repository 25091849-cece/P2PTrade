from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404

from disputes.models import Dispute
from marketplace.models import Transaction


@login_required
def index(request):
    if not request.user.is_admin():
        return redirect('transactions:index')
    return render(request, 'disputes/index.html')


@login_required
def raise_dispute(request, txn_id):
    txn = get_object_or_404(
        Transaction.objects.select_related('buyer', 'seller', 'from_currency', 'to_currency'),
        pk=txn_id,
        status='completed',
    )

    user = request.user
    if txn.buyer != user and txn.seller != user:
        raise Http404

    if hasattr(txn, 'dispute'):
        return redirect('transactions:index')

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        evidence = request.FILES.get('evidence')
        if reason:
            Dispute.objects.create(
                transaction=txn,
                buyer=txn.buyer,
                seller=txn.seller,
                raised_by=user,
                from_currency=txn.from_currency,
                to_currency=txn.to_currency,
                foreign_amount=txn.received_amount or 0,
                myr_amount=txn.amount,
                reason=reason,
                evidence=evidence,
            )
            txn.status = 'dispute_raised'
            txn.save()
            return redirect('transactions:index')

    counterparty = txn.seller if txn.buyer == user else txn.buyer
    return render(request, 'disputes/raise.html', {
        'txn': txn,
        'counterparty': counterparty,
    })


@login_required
def cancel_dispute(request, txn_id):
    if request.method != 'POST':
        return redirect('transactions:index')

    txn = get_object_or_404(
        Transaction,
        pk=txn_id,
        status='dispute_raised',
    )

    user = request.user
    if txn.buyer != user and txn.seller != user:
        raise Http404

    if hasattr(txn, 'dispute'):
        txn.dispute.delete()

    txn.status = 'completed'
    txn.save()
    return redirect('transactions:index')
