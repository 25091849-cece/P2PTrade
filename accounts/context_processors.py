from disputes.models import Dispute
from notifications.models import Notification


def is_admin_user(user):
    return bool(
        user and user.is_authenticated and (
            getattr(user, 'is_superuser', False)
            or getattr(user, 'is_staff', False)
            or getattr(user, 'is_admin', lambda: False)()
        )
    )


def admin_badges(request):
    """Expose role-aware sidebar data to all templates."""
    user = getattr(request, 'user', None)
    admin_user = is_admin_user(user)

    if not admin_user:
        return {'is_admin_user': False}

    return {
        'is_admin_user': True,
        'pending_disputes_count': Dispute.objects.filter(status='pending').count(),
        'unread_notifications_count': Notification.objects.filter(
            user=user, is_read=False,
        ).count(),
    }
