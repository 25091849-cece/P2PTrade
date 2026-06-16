from datetime import date as date_class

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.context_processors import is_admin_user
from accounts.models import User
from core.models import Currency
from disputes.models import (
    Dispute,
    DisputeActivityLog,
    DisputeMessage,
    DisputeResolution,
)
from marketplace.models import Transaction
from notifications.models import Notification


# ============================================================================
# SLA tracking — 24-hour threshold for dispute resolution
# ============================================================================
SLA_THRESHOLD_HOURS = 24


def _format_duration_label(hours):
    """Human-friendly duration label used on the SLA timeline markers."""
    if hours is None:
        return '—'
    if hours < 24:
        return 'Less than 1 Day'
    days = hours / 24
    if days < 2:
        return '1 Day'
    return f'{days:.1f} Days'


def _sla_snapshot(target_date):
    """
    Compute the Daily SLA Performance Snapshot for a given date.
    Buckets each dispute as Within (<50%), Approaching (50-90%) or Outside (>=90%)
    of the 24h SLA threshold, and returns p50/p90 processing time.
    """
    now = timezone.now()
    disputes = Dispute.objects.filter(created_at__date=target_date)

    usages = []
    processing_hours = []
    within = approaching = outside = 0

    for d in disputes:
        end_time = d.resolved_at or now
        hours = max((end_time - d.created_at).total_seconds() / 3600.0, 0.0)
        usage_pct = (hours / SLA_THRESHOLD_HOURS) * 100
        usages.append(usage_pct)
        processing_hours.append(hours)

        if usage_pct < 50:
            within += 1
        elif usage_pct < 90:
            approaching += 1
        else:
            outside += 1

    total = len(usages)
    avg_usage = round(sum(usages) / total) if total else 0

    sorted_hours = sorted(processing_hours)
    if sorted_hours:
        p50 = sorted_hours[int(total * 0.5) if int(total * 0.5) < total else total - 1]
        p90 = sorted_hours[int(total * 0.9) if int(total * 0.9) < total else total - 1]
    else:
        p50 = p90 = None

    # Position of the avg-usage marker on the 0–100% bar (clamped)
    bar_position = min(max(avg_usage, 0), 100)

    return {
        'date': target_date,
        'date_iso': target_date.isoformat(),
        'date_input': target_date.strftime('%d/%m/%Y'),
        'total': total,
        'within': within,
        'approaching': approaching,
        'outside': outside,
        'avg_usage_pct': avg_usage,
        'bar_position': bar_position,
        'p50_label': _format_duration_label(p50),
        'p90_label': _format_duration_label(p90),
        'threshold_hours': SLA_THRESHOLD_HOURS,
        'is_within_timeframe': avg_usage < 50,
    }


def _require_admin(user):
    return is_admin_user(user)


def _notify_admins_dispute_raised(dispute):
    """Notify every admin that a new dispute was submitted."""
    admins = User.objects.filter(role='admin')
    message = (
        f"New dispute #{dispute.id} on transaction #{dispute.transaction_id} "
        f"({dispute.from_currency.code} → {dispute.to_currency.code}) "
        f"raised by {dispute.raised_by.email if dispute.raised_by else 'user'}."
    )
    Notification.objects.bulk_create([
        Notification(
            user=admin,
            notification_type='dispute_raised',
            message=message,
            related_id=dispute.id,
        )
        for admin in admins
    ])


def _notify_user_dispute_resolved(dispute):
    """Notify both parties when a dispute is resolved."""
    message = f"Your dispute #{dispute.id} has been resolved."
    Notification.objects.bulk_create([
        Notification(user=dispute.buyer, notification_type='dispute_resolved',
                     message=message, related_id=dispute.id),
        Notification(user=dispute.seller, notification_type='dispute_resolved',
                     message=message, related_id=dispute.id),
    ])


# ============================================================================
# Admin: Disputes Management (list + filters + analytics)
# ============================================================================
@login_required(login_url='login')
def index(request):
    if not _require_admin(request.user):
        return redirect('transactions:index')

    qs = Dispute.objects.select_related(
        'buyer', 'seller', 'raised_by', 'from_currency', 'to_currency',
        'transaction', 'resolution',
    ).order_by('-created_at')

    status = request.GET.get('status', '')
    resolution_type = request.GET.get('resolution_type', '')
    currency = request.GET.get('currency', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if status:
        qs = qs.filter(status=status)
    if resolution_type:
        qs = qs.filter(resolution__resolution_type=resolution_type)
    if currency:
        qs = qs.filter(Q(from_currency__code=currency) | Q(to_currency__code=currency))
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    all_disputes = Dispute.objects.all()
    stats = {
        'pending': all_disputes.filter(status='pending').count(),
        'under_review': all_disputes.filter(status='under_review').count(),
        'resolved': all_disputes.filter(status='resolved').count(),
    }

    resolution_breakdown = (
        DisputeResolution.objects
        .values('resolution_type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    # SLA snapshot (date picker)
    sla_date_str = request.GET.get('sla_date', '')
    try:
        sla_date = date_class.fromisoformat(sla_date_str) if sla_date_str else timezone.now().date()
    except ValueError:
        sla_date = timezone.now().date()
    sla = _sla_snapshot(sla_date)

    return render(request, 'admin/disputes/index.html', {
        'disputes': qs,
        'stats': stats,
        'resolution_breakdown': resolution_breakdown,
        'currencies': Currency.objects.order_by('code'),
        'sla': sla,
        'filters': {
            'status': status,
            'resolution_type': resolution_type,
            'currency': currency,
            'date_from': date_from,
            'date_to': date_to,
        },
    })


# ============================================================================
# Admin: Dispute Detail (invoice viewer + resolution form)
# ============================================================================
@login_required(login_url='login')
def detail(request, dispute_id):
    if not _require_admin(request.user):
        return HttpResponseForbidden()

    dispute = get_object_or_404(
        Dispute.objects.select_related(
            'buyer', 'seller', 'raised_by', 'from_currency', 'to_currency',
            'transaction', 'resolution',
        ),
        pk=dispute_id,
    )

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'mark_under_review' and dispute.status == 'pending':
            dispute.mark_under_review()
            DisputeActivityLog.objects.create(
                dispute=dispute, actor=request.user,
                action='Marked under review by admin.',
            )
            messages.success(request, 'Dispute marked as under review.')
            return redirect('disputes:detail', dispute_id=dispute.id)

        if action == 'resolve' and dispute.status != 'resolved':
            resolution_type = request.POST.get('resolution_type', '')
            notes = request.POST.get('resolution_notes', '').strip()
            buyer_amount = request.POST.get('buyer_refund_amount') or None
            seller_amount = request.POST.get('seller_refund_amount') or None

            if resolution_type not in dict(DisputeResolution.RESOLUTION_TYPE_CHOICES):
                messages.error(request, 'Invalid resolution type.')
                return redirect('disputes:detail', dispute_id=dispute.id)

            DisputeResolution.objects.create(
                dispute=dispute,
                resolution_type=resolution_type,
                resolution_notes=notes,
                buyer_refund_amount=buyer_amount,
                seller_refund_amount=seller_amount,
                resolved_by_admin=request.user,
            )
            dispute.status = 'resolved'
            dispute.resolved_at = timezone.now()
            dispute.save()

            DisputeActivityLog.objects.create(
                dispute=dispute, actor=request.user,
                action=f'Dispute resolved: {resolution_type}.',
            )
            _notify_user_dispute_resolved(dispute)
            messages.success(request, 'Dispute resolved successfully.')
            return redirect('disputes:detail', dispute_id=dispute.id)

        if action == 'reply':
            text = request.POST.get('message', '').strip()
            if text:
                DisputeMessage.objects.create(
                    dispute=dispute, sender=request.user,
                    message=text, is_admin_message=True,
                )
            return redirect('disputes:detail', dispute_id=dispute.id)

    return render(request, 'admin/disputes/details.html', {
        'dispute': dispute,
        'resolution_choices': DisputeResolution.RESOLUTION_TYPE_CHOICES,
        'activity_logs': dispute.activity_logs.select_related('actor')[:20],
        'thread': dispute.messages.select_related('sender').all(),
    })


# ============================================================================
# User: Raise / Cancel dispute (preserves original UI; adds admin notification)
# ============================================================================

@login_required
def raise_dispute(request, txn_id):
    txn = get_object_or_404(
        Transaction.objects.select_related(
            'buyer', 'seller', 'from_currency', 'to_currency', 'deal'
        ),
        pk=txn_id,
    )

    # Disputes only make sense on P2P trade records
    if txn.type not in ('purchase', 'sale'):
        messages.error(request, 'Disputes can only be raised on purchase or sale transactions.')
        return redirect('transactions:index')

    user = request.user

    # Resolve both parties via deal (handles null buyer/seller FKs)
    if txn.deal:
        actual_seller = txn.deal.seller
        purchase_txn = txn.deal.transactions.filter(
            type='purchase'
        ).select_related('buyer').first()
        actual_buyer = purchase_txn.buyer if purchase_txn else None
    else:
        actual_buyer = txn.buyer
        actual_seller = txn.seller

    if user not in (actual_buyer, actual_seller):
        raise Http404

    if txn.status != 'completed':
        messages.error(request, f'Disputes can only be raised on completed transactions (current status: {txn.get_status_display()}).')
        return redirect('transactions:index')

    if hasattr(txn, 'dispute'):
        messages.error(request, 'A dispute already exists for this transaction.')
        return redirect('transactions:index')

    counterparty = actual_seller if user == actual_buyer else actual_buyer

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        evidence = request.FILES.get('evidence')
        if reason:
            dispute = Dispute.objects.create(
                transaction=txn,
                buyer=actual_buyer,
                seller=actual_seller,
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
            DisputeActivityLog.objects.create(
                dispute=dispute, actor=user,
                action=f'Dispute raised by {user.email}.',
            )
            _notify_admins_dispute_raised(dispute)
            return redirect('transactions:index')

    return render(request, 'disputes/raise.html', {
        'txn': txn,
        'counterparty': counterparty,
    })

@login_required
def cancel_dispute(request, txn_id):
    if request.method != 'POST':
        return redirect('transactions:index')

    # ── Remove status='dispute_raised' from the lookup ────────────────────────
    txn = get_object_or_404(Transaction, pk=txn_id)
    user = request.user

    # Resolve parties via deal
    if txn.deal:
        actual_seller = txn.deal.seller
        purchase_txn = txn.deal.transactions.filter(
            type='purchase'
        ).select_related('buyer').first()
        actual_buyer = purchase_txn.buyer if purchase_txn else None
    else:
        actual_buyer = txn.buyer
        actual_seller = txn.seller

    if user not in (actual_buyer, actual_seller):
        raise Http404

    if txn.status != 'dispute_raised':
        messages.error(request, 'This transaction does not have an active dispute.')
        return redirect('transactions:index')

    if hasattr(txn, 'dispute'):
        txn.dispute.delete()

    txn.status = 'completed'
    txn.save()
    return redirect('transactions:index')