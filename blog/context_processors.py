from .models import Notification, Genre, SiteSettings

def extras_context(request):
    """
    Makes extra data available globally to all templates.
    """
    context = {
        'all_genres': Genre.objects.all(),
        'site_settings': SiteSettings.objects.first(),
        'notifications': [],
        'unread_notifications_count': 0,
    }

    if request.user.is_authenticated:
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
        context['notifications'] = notifications[:5]  # Show top 5 in navbar dropdown
        context['unread_notifications_count'] = notifications.filter(read=False).count()

    return context
