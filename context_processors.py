from django.conf import settings
from appcore.models import Notification


def app_context(request):
    salon = request.user.salon if getattr(request.user, 'is_authenticated', False) and getattr(request.user, 'salon_id', None) else None
    unread = Notification.objects.filter(salon=salon, is_read=False).count() if salon else 0
    return {
        'APP_NAME': getattr(settings, 'APP_NAME', 'BEAUTYFLOW'),
        'CURRENT_SALON': salon,
        'DEFAULT_CURRENCY': getattr(settings, 'DEFAULT_CURRENCY', 'MAD'),
        'UNREAD_NOTIFICATIONS': unread,
    }
