from django.db import models
from django.contrib.auth.models import User
from datetime import time
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.urls import reverse
from django.utils.html import strip_tags
import re

class Group(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, help_text="Description of the group and its activities")
    logo_base64 = models.TextField(blank=True, null=True, help_text="Group logo as base64 string")
    website = models.URLField(blank=True, null=True, help_text="Group's website URL")
    contact_email = models.EmailField(blank=True, null=True, help_text="Primary contact email for the group")
    telegram_channel = models.CharField(max_length=100, blank=True, null=True, help_text="Telegram channel username (without @)")
    telegram_webhook_channel = models.CharField(
        max_length=100,
        blank=True, null=True,
        help_text="Telegram channel name for webhook posting (without @)",
        verbose_name="Telegram Webhook Channel (without @)"
    )
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('group_detail', args=[str(self.id)])
    
    def get_leadership(self):
        from users.models import GroupRole
        return GroupRole.objects.filter(group=self).order_by('assigned_at')
    
    def get_upcoming_events(self):
        from django.utils import timezone
        from datetime import datetime
        now = timezone.now()
        return self.event_set.filter(
            models.Q(date__gt=now.date()) | 
            (models.Q(date=now.date()) & models.Q(end_time__gt=now.time())),
            status='active'
        ).order_by('date', 'start_time')
    
    def get_past_events(self):
        from django.utils import timezone
        from datetime import datetime
        now = timezone.now()
        return self.event_set.filter(
            models.Q(date__lt=now.date()) | 
            (models.Q(date=now.date()) & models.Q(end_time__lt=now.time())),
            status='active'
        ).order_by('-date', '-start_time')

class Event(models.Model):
    title = models.CharField(max_length=200)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True, default=time(0, 0, 0))
    end_time = models.TimeField(null=True, blank=True, default=time(0, 0, 0))
    description = models.TextField(blank=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=50, blank=True, null=True)
    state = models.CharField(max_length=50, blank=True, null=True)
    organizer = models.ForeignKey(User, on_delete=models.CASCADE)
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Current status of the event"
    )
    AGE_CHOICES = [
        ('none', 'All ages'),
        ('adult', '18+ (Adult)'),
        ('mature', '21+ (Mature)'),
    ]
    age_restriction = models.CharField(
        max_length=10,
        choices=AGE_CHOICES,
        default='none',
        help_text="Age restriction for the event"
    )
    capacity = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Maximum number of attendees. Leave blank for no limit.",
        validators=[MinValueValidator(0)]
    )
    waitlist_enabled = models.BooleanField(default=False, help_text="Enable a waitlist if capacity is reached.")
    attendee_list_public = models.BooleanField(
        default=True,
        help_text="If false, only organizers can see the attendee list."
    )
    enable_rsvp_questions = models.BooleanField(
        default=False,
        help_text="Enable optional RSVP questions for this event."
    )
    question1_text = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Custom text for RSVP Question 1. Leave blank for default."
    )
    question2_text = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Custom text for RSVP Question 2. Leave blank for default."
    )
    question3_text = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Custom text for RSVP Question 3. Leave blank for default."
    )
    accessibility_details = models.TextField(
        blank=True,
        help_text="Describe how this event is accessible. If left blank, event is not marked as accessible."
    )
    
    def clean(self):
        if self.waitlist_enabled and self.capacity is None:
            raise ValidationError({
                'waitlist_enabled': 'Capacity must be set when waitlist is enabled.',
                'capacity': 'Capacity must be set when waitlist is enabled.'
            })
    
    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('event_detail', args=[str(self.id)])

class RSVP(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='rsvps')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rsvps', null=True, blank=True)
    name = models.CharField(max_length=100, null=True, blank=True)  # Keep for backward compatibility
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('confirmed', 'Confirmed'),
        ('waitlisted', 'Waitlisted'),
        ('maybe', 'Maybe'),
        ('not_attending', 'Not Attending')
    ], default='confirmed', null=True, blank=True)

    # Organizer-only RSVP questions
    question1 = models.CharField(max_length=255, null=True, blank=True, help_text="Organizer-only question 1 (visible only to event organizers)")
    question2 = models.CharField(max_length=255, null=True, blank=True, help_text="Organizer-only question 2 (visible only to event organizers)")
    question3 = models.CharField(max_length=255, null=True, blank=True, help_text="Organizer-only question 3 (visible only to event organizers)")
    
    # Badge customization fields
    accessibility_needs = models.BooleanField(default=False, help_text="Show accessibility indicator on badge")
    custom_rank = models.CharField(max_length=50, null=True, blank=True, help_text="Custom rank/role label for badge (e.g. 'Sponsor', 'VIP', 'Staff')")

    class Meta:
        unique_together = ['event', 'user']
        ordering = ['timestamp'] # Order by timestamp for waitlist purposes

    def __str__(self):
        if self.user:
            return f"{self.user.username} - {self.event.title}"
        return f"{self.name} - {self.event.title}"

    def remove(self):
        self.delete()

class Post(models.Model):
    title = models.CharField(max_length=300)
    content = models.TextField()
    published = models.DateTimeField()
    original_link = models.URLField(blank=True, null=True)
    guid = models.CharField(max_length=255, unique=True, blank=True, null=True)

    def __str__(self):
        return self.title

    def get_excerpt(self, length=200):
        # Remove <img> tags
        text = re.sub(r'<img[^>]*>', '', self.content)
        # Strip other HTML tags
        text = strip_tags(text)
        # Truncate
        if len(text) > length:
            return text[:length] + '…'
        return text
