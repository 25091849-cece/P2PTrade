from disputes.models import Dispute
from notifications.models import Notification


def admin_badges(request):
    """Expose unread counts to all admin templates (used by the sidebar)."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or not user.is_admin():
        return {}

    return {
        'pending_disputes_count': Dispute.objects.filter(status='pending').count(),
        'unread_notifications_count': Notification.objects.filter(
            user=user, is_read=False,
        ).count(),
    }
