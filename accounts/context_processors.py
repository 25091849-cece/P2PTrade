from disputes.models import Dispute
from notifications.models import Notification


def admin_badges(request):
    """Expose role-aware sidebar data to all templates."""
    user = getattr(request, 'user', None)
    is_admin_user = bool(user and user.is_authenticated and user.is_admin())

    if not is_admin_user:
        return {'is_admin_user': False}

    return {
        'is_admin_user': True,
        'pending_disputes_count': Dispute.objects.filter(status='pending').count(),
        'unread_notifications_count': Notification.objects.filter(
            user=user, is_read=False,
        ).count(),
    }
