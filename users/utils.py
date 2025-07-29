from users.models import Notification
from django.contrib.auth.models import User

def create_notification(user, message, link=None, event_name=None):
    """
    Creates a new notification for the specified user.
    """
    Notification.objects.create(user=user, message=message, link=link, event_name=event_name)

def approve_all_logged_in_users():
    from users.models import Profile
    users = User.objects.exclude(last_login=None)
    for user in users:
        if hasattr(user, 'profile') and not user.profile.is_verified:
            user.profile.is_verified = True
            user.profile.save()