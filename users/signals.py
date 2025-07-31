from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.contrib.auth import logout
from django.core.cache import cache
from .models import Profile, GroupRole, BannedUser

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    instance.profile.save()

@receiver(post_save, sender=BannedUser)
def handle_user_ban(sender, instance, created, **kwargs):
    """
    Handle user ban - mark user for logout on next request
    """
    if created and instance.group is None:  # Site-wide ban
        # Mark user for logout using cache
        cache_key = f"ban_logout_{instance.user.id}"
        cache.set(cache_key, True, timeout=300)  # 5 minutes timeout 