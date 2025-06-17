from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Create your models here.

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture_base64 = models.TextField(blank=True, null=True)
    is_approved_organizer = models.BooleanField(default=False)
    allowed_groups = models.ManyToManyField('events.Group', blank=True)
    display_name = models.CharField(max_length=50, blank=True, null=True)
    discord_username = models.CharField(max_length=50, blank=True, null=True)
    telegram_username = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

    def get_display_name(self):
        return self.display_name or self.user.username

    def get_initials(self):
        display_name = self.get_display_name()
        if not display_name:
            return "?"
        # Split the name and get first letter of each part
        parts = display_name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return display_name[0].upper()

    def get_avatar_color(self):
        colors = ['#1abc9c', '#2ecc71', '#3498db', '#9b59b6', '#34495e', '#16a085', '#27ae60', '#2980b9', '#8e44ad', '#2c3e50']
        color_index = sum(ord(c) for c in self.user.username) % len(colors)
        return colors[color_index]

    def get_avatar_html(self, size=40):
        if self.profile_picture_base64:
            return f'<img src="{self.profile_picture_base64}" alt="{self.get_display_name()}" class="rounded-circle" style="width: {size}px; height: {size}px; object-fit: cover;">'
        else:
            initials = self.get_initials()
            background_color = self.get_avatar_color()
            return f'<div class="rounded-circle d-flex align-items-center justify-content-center" style="width: {size}px; height: {size}px; background-color: {background_color}; color: white; font-weight: bold;">{initials}</div>'

class GroupDelegation(models.Model):
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='delegated_groups_as_organizer')
    delegated_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='delegated_groups_as_delegate')
    group = models.ForeignKey('events.Group', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('organizer', 'delegated_user', 'group')
        verbose_name = 'Assistant Assignment'
        verbose_name_plural = 'Assistant Assignments'

    def __str__(self):
        return f'{self.organizer.username} assigned {self.delegated_user.username} as an assistant for {self.group.name}'

class BannedUser(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='banned_entries')
    group = models.ForeignKey('events.Group', on_delete=models.CASCADE, null=True, blank=True)
    banned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='initiated_group_bans')
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='initiated_all_bans')
    reason = models.TextField(blank=True, null=True)
    banned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'group')
        verbose_name = "Banned User"
        verbose_name_plural = "Banned Users"

    def __str__(self):
        return f'{self.user.username} banned from {self.group.name}'

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    link = models.CharField(max_length=255, blank=True, null=True) # Optional link for the notification
    event_name = models.CharField(max_length=255, blank=True, null=True) # Optional event name for the notification

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f'Notification for {self.user.username}: {self.message[:50]}...'

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    instance.profile.save()

# The m2m_changed signal logic will be moved to signals.py
# @receiver(m2m_changed, sender=Profile.allowed_groups)
# def update_approved_organizer_status(sender, instance, action, **kwargs):
#     if action == 'post_add':
#         if not instance.is_approved_organizer:
#             instance.is_approved_organizer = True
#             instance.save()
#     elif action == 'post_remove':
#         if not instance.allowed_groups.exists() and instance.is_approved_organizer:
#             instance.is_approved_organizer = False
#             instance.save()
