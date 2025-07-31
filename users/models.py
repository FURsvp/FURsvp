from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from events.models import Group
from django.utils import timezone

# Create your models here.

class AuditLog(models.Model):
    """Audit log for tracking administrative actions and group event activities"""
    ACTION_CHOICES = [
        # User management actions
        ('user_promoted', 'User Promoted'),
        ('user_demoted', 'User Demoted'),
        ('user_banned', 'User Banned'),
        ('user_unbanned', 'User Unbanned'),
        ('user_profile_updated', 'User Profile Updated'),
        ('admin_login', 'Admin Login'),
        ('admin_logout', 'Admin Logout'),
        
        # Group management actions
        ('group_created', 'Group Created'),
        ('group_updated', 'Group Updated'),
        ('group_deleted', 'Group Deleted'),
        ('group_renamed', 'Group Renamed'),
        
        # Event management actions
        ('event_created', 'Event Created'),
        ('event_updated', 'Event Updated'),
        ('event_deleted', 'Event Deleted'),
        ('event_cancelled', 'Event Cancelled'),
        ('event_activated', 'Event Activated'),
        
        # Notification actions
        ('notification_sent', 'Notification Sent'),
        ('bulk_notification_sent', 'Bulk Notification Sent'),
        
        # Site management actions
        ('banner_updated', 'Site Banner Updated'),
        ('banner_disabled', 'Site Banner Disabled'),
        
        # Blog actions
        ('blog_post_created', 'Blog Post Created'),
        ('blog_post_deleted', 'Blog Post Deleted'),
        
        # Other actions
        ('other', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs', help_text="User who performed the action")
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='targeted_audit_logs', help_text="User who was affected by the action")
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.TextField(help_text="Detailed description of the action")
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, help_text="Group involved in the action")
    event = models.ForeignKey('events.Event', on_delete=models.SET_NULL, null=True, blank=True, help_text="Event involved in the action")
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="IP address of the user who performed the action")
    user_agent = models.TextField(blank=True, help_text="User agent string")
    timestamp = models.DateTimeField(auto_now_add=True, help_text="When the action occurred")
    additional_data = models.JSONField(default=dict, blank=True, help_text="Additional data related to the action")
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log Entry'
        verbose_name_plural = 'Audit Log Entries'
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['group', 'timestamp']),
            models.Index(fields=['target_user', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.username if self.user else 'System'} - {self.get_action_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    
    @classmethod
    def log_action(cls, user, action, description, target_user=None, group=None, event=None, ip_address=None, user_agent=None, additional_data=None):
        """Convenience method to create an audit log entry"""
        return cls.objects.create(
            user=user,
            action=action,
            description=description,
            target_user=target_user,
            group=group,
            event=event,
            ip_address=ip_address,
            user_agent=user_agent,
            additional_data=additional_data or {}
        )

class GroupRole(models.Model):
    """Custom hierarchy system for group leadership roles"""
    group = models.ForeignKey('events.Group', on_delete=models.CASCADE, related_name='group_roles')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_roles')
    assigned_at = models.DateTimeField(auto_now_add=True)
    custom_label = models.CharField(max_length=64, blank=True, null=True)
    can_post = models.BooleanField(default=False)
    can_manage_leadership = models.BooleanField(default=False)

    class Meta:
        unique_together = ('group', 'user')
        ordering = ['assigned_at']
        verbose_name = 'Group Role'
        verbose_name_plural = 'Group Roles'

    def __str__(self):
        label = self.custom_label or self.user.username
        return f"{self.user.username} - {label} ({self.group.name})"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
    
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture_base64 = models.TextField(blank=True, null=True)
    display_name = models.CharField(max_length=50, blank=True, null=True)
    discord_username = models.CharField(max_length=50, blank=True, null=True)
    telegram_username = models.CharField(max_length=50, blank=True, null=True)
    telegram_id = models.BigIntegerField(blank=True, null=True, unique=True, help_text="Telegram user ID for authentication")
    can_post_blog = models.BooleanField(default=False, help_text='Can post blog posts')
    is_verified = models.BooleanField(default=False, help_text='Has the user verified their email?')
    verification_token = models.CharField(max_length=64, blank=True, null=True, help_text='Email verification token')

    class Meta:
        permissions = [
            ("can_post_blog", "Can post blog posts")
        ]

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
