from django.shortcuts import render, get_object_or_404, redirect
from .models import Event, RSVP, Post, Group
from django.utils import timezone
from datetime import timedelta, datetime
from django.contrib.auth.decorators import login_required
from .forms import EventForm, RSVPForm, Group
from users.models import Profile, GroupDelegation, BannedUser, Notification, GroupRole
from django.contrib import messages
from django.db import models, transaction
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from users.utils import create_notification
import feedparser
from django.views.generic import ListView, DetailView
import pytz
import time
from events.forms import GroupRoleForm
from django.db.models import Q
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
import calendar
from django.forms.utils import ErrorList
from events.utils import post_to_telegram_channel
from django.urls import reverse
import os
import json
import requests
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_GET

# Create your views here.

def get_telegram_feed(channel='', limit=5):
    url = f"https://rss.tabithahanegan.com/telegram/channel/{channel}"
    if url == "https://rss.tabithahanegan.com/telegram/channel/None":
        url = ""
    feed = feedparser.parse(url)
    entries = feed.entries[:limit]
    eastern = pytz.timezone('America/New_York')
    for entry in entries:
        # Try published_parsed first
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            dt_utc = datetime.fromtimestamp(time.mktime(entry.published_parsed), pytz.utc)
            entry.est_datetime = dt_utc.astimezone(eastern)
        # Fallback: try published (RFC822 string)
        elif hasattr(entry, 'published') and entry.published:
            try:
                dt_utc = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %Z')
                dt_utc = pytz.utc.localize(dt_utc)
                entry.est_datetime = dt_utc.astimezone(eastern)
            except Exception:
                entry.est_datetime = None
        else:
            entry.est_datetime = None
    return entries

def get_bluesky_feed(profile='fursvp.org', limit=10):
    url = f"https://rss.tabithahanegan.com/bsky/profile/{profile}"
    feed = feedparser.parse(url)
    entries = feed.entries[:limit]
    eastern = pytz.timezone('America/New_York')
    for entry in entries:
        # Try published_parsed first
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            dt_utc = datetime.fromtimestamp(time.mktime(entry.published_parsed), pytz.utc)
            entry.est_datetime = dt_utc.astimezone(eastern)
        elif hasattr(entry, 'published') and entry.published:
            try:
                dt_utc = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %Z')
                dt_utc = pytz.utc.localize(dt_utc)
                entry.est_datetime = dt_utc.astimezone(eastern)
            except Exception:
                entry.est_datetime = None
        else:
            entry.est_datetime = None
    return entries


def home(request):
    # Get sort parameters from request
    sort_by = request.GET.get('sort', 'date')  # Default sort by date
    sort_order = request.GET.get('order', 'asc')  # Default ascending order
    filter_adult = request.GET.get('adult', 'true') # Default to show adult events
    view_type = request.GET.get('view', 'list')  # Default to list view
    page = request.GET.get('page', 1)  # Default to first page
    
    # Get year and month for calendar vieww
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    search_query = request.GET.get('search', '').strip()
    state_filter = request.GET.get('state', '').strip()
    
    # Base queryset - filter out events that have already passed and cancelled events
    now = timezone.now()
    events = Event.objects.filter(
        models.Q(date__gt=now.date()) | 
        (models.Q(date=now.date()) & models.Q(end_time__gt=now.time())),
        status='active'  # Only show active events
    )

    if filter_adult == 'false':
        events = events.exclude(age_restriction__in=['adult', 'mature'])

    # Apply search filter
    if search_query:
        events = events.filter(
            models.Q(title__icontains=search_query) |
            models.Q(description__icontains=search_query) |
            models.Q(city__icontains=search_query) |
            models.Q(group__name__icontains=search_query)
        )

    # Apply state filter
    if state_filter:
        events = events.filter(state__iexact=state_filter)

    events = events.annotate(
        confirmed_count=models.Count('rsvps', filter=models.Q(rsvps__status='confirmed'))
    )
    
    # Add user's RSVP information if user is authenticated
    if request.user.is_authenticated:
        events = events.annotate(
            user_rsvp_status=models.Subquery(
                RSVP.objects.filter(
                    event=models.OuterRef('pk'),
                    user=request.user
                ).values('status')[:1]
            )
        )
        
        # Add user's RSVP list for template compatibility
        for event in events:
            user_rsvp = event.rsvps.filter(user=request.user).first()
            if user_rsvp:
                event.user_rsvp_list = [user_rsvp]
            else:
                event.user_rsvp_list = []
    
    # Apply sorting
    if sort_by == 'date':
        events = events.order_by('date', 'start_time') if sort_order == 'asc' else events.order_by('-date', '-start_time')
    elif sort_by == 'group':
        events = events.order_by(models.functions.Lower('group__name') if sort_order == 'asc' else models.functions.Lower('group__name').desc())
    elif sort_by == 'title':
        events = events.order_by(models.functions.Lower('title') if sort_order == 'asc' else models.functions.Lower('title').desc())
    elif sort_by == 'rsvps':
        events = events.annotate(rsvp_count=models.Count('rsvps')).order_by(
            'rsvp_count' if sort_order == 'asc' else '-rsvp_count'
        )
    
    # Pagination
    paginator = Paginator(events, 12)  # Show 12 events per page
    try:
        events_page = paginator.page(page)
    except PageNotAnInteger:
        events_page = paginator.page(1)
    except EmptyPage:
        events_page = paginator.page(paginator.num_pages)
    
    # Add user's RSVP information if user is authenticated (AFTER pagination)
    if request.user.is_authenticated:
        # Add user's RSVP list for template compatibility
        for event in events_page:
            user_rsvp = event.rsvps.filter(user=request.user).first()
            if user_rsvp:
                event.user_rsvp_list = [user_rsvp]
            else:
                event.user_rsvp_list = []
    
    # Calendar data
    if view_type == 'calendar':
        # Set first weekday to Sunday
        calendar.setfirstweekday(calendar.SUNDAY)
        # Create calendar object
        cal = calendar.monthcalendar(year, month)
        month_name = calendar.month_name[month]
        
        # Get events for this month
        start_date = datetime(year, month, 1).date()
        if month == 12:
            end_date = datetime(year + 1, 1, 1).date()
        else:
            end_date = datetime(year, month + 1, 1).date()
        
        month_events = events.filter(
            date__gte=start_date,
            date__lt=end_date
        ).order_by('date', 'start_time')
        
        # Group events by date
        events_by_date = {}
        for event in month_events:
            date_key = event.date.strftime('%Y-%m-%d')
            if date_key not in events_by_date:
                events_by_date[date_key] = []
            events_by_date[date_key].append(event)
        
        # Navigation
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        
        eastern = pytz.timezone('America/New_York')
        today = timezone.now().astimezone(eastern).date()
        calendar_data = {
            'calendar': cal,
            'month_name': month_name,
            'year': year,
            'month': month,
            'events_by_date': events_by_date,
            'prev_month': prev_month,
            'prev_year': prev_year,
            'next_month': next_month,
            'next_year': next_year,
            'today': today,
        }
    else:
        calendar_data = None
    
    # Get all unique states for the dropdown
    all_states = Event.objects.exclude(state__isnull=True).exclude(state__exact='').values_list('state', flat=True).distinct().order_by('state')
    
    # Calculate actual statistics
    from django.contrib.auth.models import User
    from .models import PlatformStats
    
    # Get cumulative stats that always increase
    stats = PlatformStats.get_or_create_stats()
    
    # Active events (current and future)
    active_events = Event.objects.filter(
        models.Q(date__gte=now.date()) | 
        (models.Q(date=now.date()) & models.Q(end_time__gt=now.time())),
        status='active'
    ).count()
    
    context = {
        'events': events_page,
        'current_sort': sort_by,
        'current_order': sort_order,
        'filter_adult': filter_adult,
        'view_type': view_type,
        'calendar_data': calendar_data,
        'paginator': paginator,
        'page_obj': events_page,
        'today': timezone.now().date(),
        'all_states': all_states,
        'events_count': stats.total_events_created,
        'groups_count': stats.total_groups_created,
        'users_count': stats.total_users_registered,
        'rsvps_count': stats.total_rsvps_created,
        'active_events_count': active_events,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # If it's an AJAX request, only return the partial event list HTML
        return render(request, 'events/events_list_partial.html', context)
    
    # For regular requests, render the full page
    return render(request, 'events/home.html', context)

def event_detail(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    rsvps = event.rsvps.all().select_related('user__profile')
    
    # Calculate if event has passed
    event_end_datetime = datetime.combine(event.date, event.end_time)
    # Make event_end_datetime timezone-aware if USE_TZ is True in settings
    if timezone.is_aware(timezone.now()):
        event_end_datetime = timezone.make_aware(event_end_datetime, timezone.get_current_timezone())

    event_has_passed = timezone.now() > event_end_datetime

    # Get user's RSVP if they're logged in
    user_rsvp = None
    is_site_admin = request.user.is_authenticated and request.user.is_superuser
    is_organizer_of_this_event = request.user.is_authenticated and event.organizer == request.user

    # Check if user is an approved organizer for this group or a delegated assistant
    can_access_group_contact_info = False
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            if GroupRole.objects.filter(user=profile.user, group=event.group).exists():
                can_access_group_contact_info = True
        except Profile.DoesNotExist:
            pass

        if not can_access_group_contact_info and event.group:
            if GroupDelegation.objects.filter(delegated_user=request.user, group=event.group).exists():
                can_access_group_contact_info = True

    if request.user.is_authenticated:
        user_rsvp = event.rsvps.filter(user=request.user).first()

    can_ban_user = is_organizer_of_this_event or is_site_admin
    can_view_contact_info = is_organizer_of_this_event or is_site_admin or can_access_group_contact_info
    can_cancel_event = is_organizer_of_this_event or is_site_admin

    # Check if the user is banned by this event's organizer (for any group)
    is_banned_by_organizer = False
    if request.user.is_authenticated and event.organizer:
        is_banned_by_organizer = BannedUser.objects.filter(user=request.user, organizer=event.organizer).exists()

    # Check if the user is banned from this specific group
    is_banned_from_group = False
    if request.user.is_authenticated and event.group:
        is_banned_from_group = BannedUser.objects.filter(user=request.user, group=event.group).exists()

    # Calculate confirmed RSVPs and waitlisted RSVPs
    confirmed_rsvps_count = event.rsvps.filter(status='confirmed').count()
    waitlisted_rsvps_count = event.rsvps.filter(status='waitlisted').count()

    is_event_full = False
    can_join_waitlist = False
    if event.capacity is not None:
        if confirmed_rsvps_count >= event.capacity:
            is_event_full = True
            if event.waitlist_enabled:
                can_join_waitlist = True

    def promote_waitlisted_if_spot(event):
        if event.waitlist_enabled and event.capacity is not None:
            current_confirmed_count = event.rsvps.filter(status='confirmed').count()
            if current_confirmed_count < event.capacity:
                oldest_waitlisted_rsvp = event.rsvps.filter(
                    status='waitlisted'
                ).order_by('timestamp').first()
                if oldest_waitlisted_rsvp:
                    oldest_waitlisted_rsvp.status = 'confirmed'
                    oldest_waitlisted_rsvp.timestamp = timezone.now()
                    oldest_waitlisted_rsvp.save()
                    if oldest_waitlisted_rsvp.user:
                        create_notification(
                            oldest_waitlisted_rsvp.user,
                            f'You have been moved from the waitlist to confirmed for {event.title}!',
                            link=event.get_absolute_url()
                        )

    if request.method == 'POST' and request.user.is_authenticated:
        # Prevent banned users from RSVPing
        if is_banned_by_organizer or is_banned_from_group:
            messages.error(request, 'You are banned from RSVPing to events by this organizer or group.', extra_tags='admin_notification')
            return redirect('event_detail', event_id=event.id)

        if 'cancel_event' in request.POST and can_cancel_event:
            with transaction.atomic():
                event.status = 'cancelled'
                event.save()
                
                # Notify all confirmed and waitlisted attendees
                for rsvp in event.rsvps.filter(status__in=['confirmed', 'waitlisted']):
                    if rsvp.user:
                        create_notification(
                            rsvp.user,
                            f'Event "{event.title}" has been cancelled.',
                            link=event.get_absolute_url()
                        )
                
                return redirect('event_detail', event_id=event.id)

        if 'remove_rsvp' in request.POST:
            if user_rsvp: # Ensure there is an RSVP to remove
                with transaction.atomic():
                    was_confirmed = (user_rsvp.status == 'confirmed')
                    user_rsvp.delete()
                    create_notification(request.user, f'You have removed your RSVP for {event.title}.', link=event.get_absolute_url())
                    # Telegram webhook for public RSVP removal
                    if event.attendee_list_public and event.group and getattr(event.group, 'telegram_webhook_channel', None):
                        telegram_username = None
                        if hasattr(request.user, 'profile') and getattr(request.user.profile, 'telegram_username', None):
                            telegram_username = request.user.profile.telegram_username
                        if telegram_username:
                            mention = f'@{telegram_username}'
                        else:
                            mention = request.user.get_username() if request.user else 'Someone'
                        date_str = event.date.strftime('%m/%d/%Y') if hasattr(event.date, 'strftime') else str(event.date)
                        event_url = request.build_absolute_uri(event.get_absolute_url())
                        msg = (
                            f'❌ {mention} removed their RSVP for [{event.title}]({event_url}).\n'
                            f'*Date:* {date_str}\n'
                            f'*Group:* {event.group.name}'
                        )
                        post_to_telegram_channel(event.group.telegram_webhook_channel, msg, parse_mode="Markdown")
                    # If a confirmed spot opened up and waitlist is enabled, promote oldest waitlisted
                    if was_confirmed:
                        promote_waitlisted_if_spot(event)
            else:
                messages.error(request, 'You do not have an RSVP to remove.', extra_tags='admin_notification')
            return redirect('event_detail', event_id=event.id)
        
        if 'delete_event' in request.POST and can_ban_user:
            event_title = event.title
            event_url = request.build_absolute_uri(event.get_absolute_url())
            event.delete()
            create_notification(request.user, f'Event "{event_title}" has been deleted.', link='/') # Link to home since event is deleted
            # Telegram webhook for event deletion
            if event.group and getattr(event.group, 'telegram_webhook_channel', None):
                msg = (
                    f'🚫 *Event Deleted!*\n'
                    f'*Title:* [{event_title}]({event_url})\n'
                    f'*Group:* {event.group.name}'
                )
                post_to_telegram_channel(event.group.telegram_webhook_channel, msg, parse_mode="Markdown")
            return redirect('home')
            
        form = RSVPForm(request.POST, instance=user_rsvp, event=event)
        if form.is_valid():
            new_status = form.cleaned_data['status']
            rsvp = form.save(commit=False)
            rsvp.event = event
            rsvp.user = request.user
            rsvp.save()
            create_notification(request.user, f'Your RSVP status has been updated to {rsvp.get_status_display()!s} for {event.title}.', link=event.get_absolute_url())
            # Telegram webhook for public RSVP (any status)
            if event.attendee_list_public and event.group and getattr(event.group, 'telegram_webhook_channel', None):
                telegram_username = None
                if hasattr(request.user, 'profile') and getattr(request.user.profile, 'telegram_username', None):
                    telegram_username = request.user.profile.telegram_username
                if telegram_username:
                    mention = f'@{telegram_username}'
                else:
                    mention = request.user.get_username() if request.user else 'Someone'
                date_str = event.date.strftime('%m/%d/%Y') if hasattr(event.date, 'strftime') else str(event.date)
                event_url = request.build_absolute_uri(event.get_absolute_url())
                status_emoji = {
                    'confirmed': '✅',
                    'waitlisted': '⏳',
                    'maybe': '❔',
                    'not_attending': '🚫'
                }.get(new_status, '')
                msg = (
                    f'{status_emoji} {mention} RSVP\'d as *{rsvp.get_status_display()}* for [{event.title}]({event_url}).\n'
                    f'*Date:* {date_str}\n'
                    f'*Group:* {event.group.name}'
                )
                post_to_telegram_channel(event.group.telegram_webhook_channel, msg, parse_mode="Markdown")
            return redirect('event_detail', event_id=event.id)
        else:
            messages.error(request, f'Error updating RSVP: {form.errors}', extra_tags='admin_notification')

    elif 'update_rsvp_status_by_organizer' in request.POST:
        if not can_ban_user: # Use the new flag
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)
        
        rsvp_id = request.POST.get('rsvp_id')
        new_status = request.POST.get('new_status')

        response_data = {}
        status_code = 200

        try:
            rsvp_to_update = event.rsvps.get(id=rsvp_id)
            
            with transaction.atomic():
                old_status = rsvp_to_update.status
                rsvp_to_update.status = new_status
                rsvp_to_update.save()

                message = f"{rsvp_to_update.user.username}'s RSVP for {event.title} updated to {rsvp_to_update.get_status_display()}."
                create_notification(request.user, message, link=event.get_absolute_url())
                # Send a notification to the user whose RSVP was updated
                if rsvp_to_update.user:
                    create_notification(rsvp_to_update.user, f'Your RSVP for {event.title} has been updated to {rsvp_to_update.get_status_display()}. (by {request.user.username})', link=event.get_absolute_url())

                # If a confirmed spot was freed up and new status is NOT confirmed
                if old_status == 'confirmed' and new_status != 'confirmed':
                    if event.waitlist_enabled and event.capacity is not None:
                        # Synchronously promote the oldest waitlisted user
                        promote_waitlisted_if_spot(event)
                
                # If changing from waitlisted to confirmed
                elif old_status == 'waitlisted' and new_status == 'confirmed':
                    pass # Logic already handles the count update by saving

                response_data = {'status': 'success', 'message': message}
                status_code = 200

        except RSVP.DoesNotExist:
            response_data = {'status': 'error', 'message': 'RSVP not found.'}
            status_code = 404
        except Exception as e:
            response_data = {'status': 'error', 'message': f'An error occurred: {str(e)}'}
            status_code = 500
        
        return JsonResponse(response_data, status=status_code)

    else:
        # Always use instance=user_rsvp for the RSVP form if user_rsvp exists
        form = RSVPForm(instance=user_rsvp, event=event)
    
    # Add EventForm for the edit event modal
    event_form = None
    edit_event_errors = None
    edit_event_post = None
    if request.user.is_authenticated:
        # Check for edit errors in session (from failed edit_event POST)
        edit_event_errors = request.session.pop('edit_event_errors', None)
        edit_event_post = request.session.pop('edit_event_post', None)
        if edit_event_post:
            event_form = EventForm(edit_event_post, instance=event, user=request.user)
            # Manually assign errors to the form, converting lists back to ErrorList
            if edit_event_errors:
                event_form._errors = {}
                for k, v in edit_event_errors.items():
                    event_form._errors[k] = ErrorList(v)
        else:
            event_form = EventForm(instance=event, user=request.user)

    # Get ban status for each RSVP user (for initial rendering)
    # And filter by status for display
    all_rsvps_data = []
    # Use prefetch_related for user__profile to reduce queries
    rsvps_queryset = event.rsvps.all().select_related('user__profile').order_by('timestamp')

    for rsvp in rsvps_queryset:
        is_banned = False
        # Check for group ban first
        if event.group:
            is_banned = BannedUser.objects.filter(user=rsvp.user, group=event.group).exists()
        # If not group banned, check for organizer ban (if event has an organizer)
        if not is_banned and event.organizer:
            is_banned = BannedUser.objects.filter(user=rsvp.user, organizer=event.organizer).exists()
        # If not group or organizer banned, check for site-wide ban
        if not is_banned:
            is_banned = BannedUser.objects.filter(user=rsvp.user, group__isnull=True, organizer__isnull=True).exists()

        all_rsvps_data.append({'rsvp': rsvp, 'is_banned': is_banned})

    # Group RSVPs by status for template display
    confirmed_rsvps = [r for r in all_rsvps_data if r['rsvp'].status == 'confirmed']
    waitlisted_rsvps = [r for r in all_rsvps_data if r['rsvp'].status == 'waitlisted']
    maybe_rsvps = [r for r in all_rsvps_data if r['rsvp'].status == 'maybe']
    not_attending_rsvps = [r for r in all_rsvps_data if r['rsvp'].status == 'not_attending']

    # Construct a well-formatted location string
    location_components = []
    if event.address:
        location_components.append(event.address)
    
    city_state_parts = []
    if event.city:
        city_state_parts.append(event.city)
    if event.state:
        city_state_parts.append(event.state)
    
    if city_state_parts:
        location_components.append(", ".join(city_state_parts))
    
    # Do NOT include county in location_components
    location_display_string = ", ".join(filter(None, location_components)) # filter(None, ...) removes empty strings

    # Check if user is an organizer or has group access
    # (is_organizer is already calculated above)

    # Determine if the RSVP form should be displayed
    show_rsvp_form = (not is_event_full or can_join_waitlist) or \
                     (user_rsvp is not None and user_rsvp.status != 'confirmed')

    # Determine attendee list visibility
    can_view_attendee_list = (
        event.attendee_list_public or
        is_organizer_of_this_event or
        is_site_admin or
        can_access_group_contact_info
    )

    # If attendee list is hidden, but user has an RSVP, only show their RSVP in the list
    if not can_view_attendee_list and user_rsvp:
        def only_user_rsvp(group, status):
            if user_rsvp.status == status:
                return [{'rsvp': user_rsvp, 'is_banned': False}]
            return []
        confirmed_rsvps = only_user_rsvp(confirmed_rsvps, 'confirmed')
        waitlisted_rsvps = only_user_rsvp(waitlisted_rsvps, 'waitlisted')
        maybe_rsvps = only_user_rsvp(maybe_rsvps, 'maybe')
        not_attending_rsvps = only_user_rsvp(not_attending_rsvps, 'not_attending')
    elif not can_view_attendee_list and not user_rsvp:
        confirmed_rsvps = []
        waitlisted_rsvps = []
        maybe_rsvps = []
        not_attending_rsvps = []

    context = {
        'event': event,
        'rsvps': rsvps,
        'form': form,
        'event_form': event_form,
        'user_rsvp': user_rsvp,
        'is_organizer': is_organizer_of_this_event,
        'is_site_admin': is_site_admin,
        'event_has_passed': event_has_passed,
        'confirmed_rsvps_count': confirmed_rsvps_count,
        'waitlisted_rsvps_count': waitlisted_rsvps_count,
        'is_event_full': is_event_full,
        'can_join_waitlist': can_join_waitlist,
        'can_ban_user': can_ban_user,
        'location_display_string': location_display_string,
        'rsvp_groups': {
            'confirmed': confirmed_rsvps,
            'waitlisted': waitlisted_rsvps,
            'maybe': maybe_rsvps,
            'not_attending': not_attending_rsvps,
        },
        'can_view_contact_info': can_view_contact_info,
        'show_rsvp_form': show_rsvp_form,
        'can_cancel_event': can_cancel_event,
        'can_view_attendee_list': can_view_attendee_list,
        'edit_event_errors': edit_event_errors,
        'edit_event_post': edit_event_post,
    }
    return render(request, 'events/event_detail.html', context)

@login_required
def create_event(request):
    # Check if user is a group leader, an assistant, or an admin
    is_leader = GroupRole.objects.filter(user=request.user).exists()
    is_assistant = GroupDelegation.objects.filter(delegated_user=request.user).exists()
    
    # Admins can always create events
    if not (request.user.is_superuser or is_leader or is_assistant):
        return redirect('pending_approval')

    if request.method == 'POST':
        form = EventForm(request.POST, user=request.user)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = request.user
            event.save()
            # Telegram webhook for new event
            group = event.group
            if group and getattr(group, 'telegram_webhook_channel', None):
                date_str = event.date.strftime('%m/%d/%Y') if hasattr(event.date, 'strftime') else str(event.date)
                event_url = request.build_absolute_uri(event.get_absolute_url())
                msg = (
                    "🎉 *New Event Created!*\n"
                    f"*Title:* [{event.title}]({event_url})\n"
                    f"*Date:* {date_str}\n"
                    f"*Group:* {group.name}"
                )
                post_to_telegram_channel(group.telegram_webhook_channel, msg, parse_mode="Markdown")
            return redirect('event_detail', event_id=event.id)
    else:
        form = EventForm(user=request.user)
    return render(request, 'events/event_create.html', {'form': form})

@login_required
def edit_event(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    if request.user != event.organizer and not request.user.is_superuser:
        messages.error(request, "You are not authorized to edit this event.")
        return redirect('event_detail', event_id=event.id)

    # Only check group role/delegation if user is not the organizer or superuser
    if not request.user.is_superuser and request.user != event.organizer:
        is_delegated_assistant = False
        if request.user.is_authenticated and event.group:
            is_delegated_assistant = GroupDelegation.objects.filter(delegated_user=request.user, group=event.group, organizer=event.organizer).exists()
        is_leader = GroupRole.objects.filter(user=request.user, group=event.group).exists()
        if not (is_leader or is_delegated_assistant):
            messages.error(request, "You are not authorized to edit events for this group.")
            return redirect('event_detail', event_id=event.id)

    if request.method == 'POST':
        form = EventForm(request.POST, instance=event, user=request.user)
        if form.is_valid():
            event = form.save(commit=False)
            if not event.organizer:
                event.organizer = request.user
            event.save()
            create_notification(request.user, f'Event for {event.title} updated successfully!', link=event.get_absolute_url())
            for rsvp in event.rsvps.select_related('user').all():
                if rsvp.user and rsvp.user != request.user:
                    create_notification(
                        rsvp.user,
                        f'The event "{event.title}" you RSVP\'d to has been updated. Please review the changes.',
                        link=event.get_absolute_url()
                    )
            return redirect('event_detail', event_id=event.id)
        else:
            # Store form errors and POST data in session, converting ErrorList to plain lists
            plain_errors = {k: list(map(str, v)) for k, v in form.errors.items()}
            request.session['edit_event_errors'] = plain_errors
            request.session['edit_event_post'] = request.POST
            return redirect(f'{event.get_absolute_url()}?edit=1')
    else:
        # Redirect GET requests to event detail with ?edit=1 to trigger modal
        return redirect(f'{event.get_absolute_url()}?edit=1')

@login_required
def uncancel_event(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    if request.user != event.organizer and not request.user.is_superuser:
        messages.error(request, "You are not authorized to uncancel this event.")
        return redirect('event_detail', event_id=event.id)

    if request.method == 'POST':
        with transaction.atomic():
            event.status = 'active'
            event.save()
            
            # Notify all users who had RSVPs
            for rsvp in event.rsvps.all():
                if rsvp.user:
                    create_notification(
                        rsvp.user,
                        f'Event "{event.title}" has been uncancelled.',
                        link=event.get_absolute_url()
                    )
            
            return redirect('event_detail', event_id=event.id)
    
    return redirect('event_detail', event_id=event.id)

def terms(request):
    return render(request, 'events/terms.html')

def faq(request):
    return render(request, 'events/faq.html')

def eula(request):
    return render(request, 'events/eula.html')

def privacy(request):
    return render(request, 'events/privacy.html')

def group_detail(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    
    # Remove legacy organizers and assistants
    organizers = []
    assistants = []
    
    # Get upcoming and past events
    upcoming_events = group.get_upcoming_events()
    past_events = group.get_past_events()[:10]  # Limit to 10 most recent past events
    
    # Check if user can edit this group
    can_edit_group = False
    if request.user.is_authenticated:
        can_edit_group = (
            request.user.is_superuser or 
            GroupRole.objects.filter(user=request.user, group=group).filter(
                Q(can_post=True) | Q(can_manage_leadership=True)
            ).exists()
        )
    
    # Handle POST requests
    if request.method == 'POST' and can_edit_group:
        # Handle group editing
        if 'edit_group' in request.POST:
            try:
                # Update group fields
                group.name = request.POST.get('name', group.name)
                group.description = request.POST.get('description', group.description)
                group.website = request.POST.get('website', group.website)
                group.contact_email = request.POST.get('contact_email', group.contact_email)
                group.telegram_channel = request.POST.get('telegram_channel', group.telegram_channel)
                group.telegram_webhook_channel = request.POST.get('telegram_webhook_channel', group.telegram_webhook_channel)
                
                # Handle logo upload
                logo_base64 = request.POST.get('logo_base64')
                if logo_base64:
                    group.logo_base64 = logo_base64
                
                group.save()
                messages.success(request, f'Group "{group.name}" has been updated successfully.')
                return redirect('group_detail', group_id=group.id)
                
            except Exception as e:
                messages.error(request, f'Error updating group: {str(e)}')
        
        # Handle leadership management
        elif 'add_leader' in request.POST:
            form = GroupRoleForm(request.POST, group=group)
            if form.is_valid():
                role = form.save(commit=False)
                role.group = group
                # If this is the first leader for the group, give all permissions
                if GroupRole.objects.filter(group=group).count() == 0:
                    role.can_post = True
                    role.can_manage_leadership = True
                role.save()
                messages.success(request, 'Leader added successfully.')
            else:
                messages.error(request, 'Error adding leader. Please check the form.')
            return redirect('group_detail', group_id=group.id)
        
        elif 'edit_leader' in request.POST:
            role_id = request.POST.get('role_id')
            try:
                role = GroupRole.objects.get(pk=role_id, group=group)
                role.custom_label = request.POST.get('custom_label', role.custom_label)
                role.can_manage_leadership = bool(request.POST.get('can_manage_leadership'))
                role.save()
                messages.success(request, 'Leader updated successfully.')
            except GroupRole.DoesNotExist:
                messages.error(request, 'Leader not found.')
            return redirect('group_detail', group_id=group.id)
        
        elif 'remove_leader' in request.POST:
            role_id = request.POST.get('role_id')
            try:
                role = GroupRole.objects.get(pk=role_id, group=group)
                role.delete()
                messages.success(request, 'Leader removed successfully.')
            except GroupRole.DoesNotExist:
                messages.error(request, 'Leader not found.')
            return redirect('group_detail', group_id=group.id)
    
    # Get Telegram feed for this group (if channel set), else default
    telegram_channel = group.telegram_channel
    telegram_feed = get_telegram_feed(telegram_channel)

    # Leadership roles and form
    leadership_roles = GroupRole.objects.filter(group=group).select_related('user')
    leadership_form = GroupRoleForm(group=group)
    
    context = {
        'group': group,
        'organizers': organizers,
        'assistants': assistants,
        'upcoming_events': upcoming_events,
        'past_events': past_events,
        'can_edit_group': can_edit_group,
        'telegram_feed': telegram_feed,
        'leadership_roles': leadership_roles,
        'leadership_form': leadership_form,
        'can_manage_leadership': can_edit_group,  # or use your own logic
    }
    
    return render(request, 'events/group_detail.html', context)

@login_required
def manage_group_leadership(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    user_roles = GroupRole.objects.filter(group=group, user=request.user)
    can_manage = user_roles.filter(can_manage_leadership=True).exists() or request.user.is_superuser
    if not can_manage:
        return HttpResponseForbidden('You do not have permission to manage leadership.')

    if request.method == 'POST':
        if 'add_leader' in request.POST:
            form = GroupRoleForm(request.POST, group=group)
            if form.is_valid():
                role = form.save(commit=False)
                role.group = group
                # If this is the first leader for the group, give all permissions
                if GroupRole.objects.filter(group=group).count() == 0:
                    role.can_post = True
                    role.can_manage_leadership = True
                role.save()
                messages.success(request, 'Leader added successfully.')
            else:
                messages.error(request, 'Error adding leader. Please check the form.')
            return redirect('group_detail', group_id=group.id)
        elif 'edit_leader' in request.POST:
            role_id = request.POST.get('role_id')
            role = get_object_or_404(GroupRole, pk=role_id, group=group)
            form = GroupRoleForm(request.POST, instance=role, group=group)
            if form.is_valid():
                form.save()
                return JsonResponse({'success': True, 'msg': 'Leader updated successfully.'})
            else:
                return JsonResponse({'success': False, 'errors': form.errors})
        elif 'remove_leader' in request.POST:
            role_id = request.POST.get('role_id')
            role = get_object_or_404(GroupRole, pk=role_id, group=group)
            role.delete()
            return JsonResponse({'success': True, 'msg': 'Leader removed successfully.'})
    else:
        roles = GroupRole.objects.filter(group=group).select_related('user')
        form = GroupRoleForm(group=group)
        return render(request, 'events/leadership_editor.html', {'group': group, 'roles': roles, 'form': form, 'can_manage': can_manage})

def groups_list(request):
    search_query = request.GET.get('search', '').strip()
    groups = Group.objects.all()
    if search_query:
        groups = groups.filter(
            models.Q(name__icontains=search_query) |
            models.Q(description__icontains=search_query)
        )
    groups = groups.order_by('name')
    paginator = Paginator(groups, 9)  # 9 groups per page
    page = request.GET.get('page', 1)
    try:
        paginated_groups = paginator.page(page)
    except PageNotAnInteger:
        paginated_groups = paginator.page(1)
    except EmptyPage:
        paginated_groups = paginator.page(paginator.num_pages)
    context = {
        'groups': paginated_groups,
        'search_query': search_query,
    }
    return render(request, 'events/groups_list.html', context)

def event_index(request):
    """Calendar view with all events underneath"""
    # Get year and month from request, default to current
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    # Get filter parameters for events list
    sort_by = request.GET.get('sort', 'date')
    sort_order = request.GET.get('order', 'asc')
    filter_adult = request.GET.get('adult', 'true')
    view_type = request.GET.get('view', 'list')
    page = request.GET.get('page', 1)
    search_query = request.GET.get('search', '').strip()
    state_filter = request.GET.get('state', '').strip()
    mileage_range = request.GET.get('mileage', '50')  # Default 50 miles
    
    # Set first weekday to Sunday
    calendar.setfirstweekday(calendar.SUNDAY)
    # Create calendar object
    cal = calendar.monthcalendar(year, month)
    # Get month name
    month_name = calendar.month_name[month]
    # Get events for this month
    start_date = datetime(year, month, 1).date()
    if month == 12:
        end_date = datetime(year + 1, 1, 1).date()
    else:
        end_date = datetime(year, month + 1, 1, 1).date()
    calendar_events = Event.objects.filter(
        date__gte=start_date,
        date__lt=end_date,
        status='active'
    ).order_by('date', 'start_time')
    # Group events by date
    events_by_date = {}
    for event in calendar_events:
        date_key = event.date.strftime('%Y-%m-%d')
        if date_key not in events_by_date:
            events_by_date[date_key] = []
        events_by_date[date_key].append(event)
    # Navigation
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    eastern = pytz.timezone('America/New_York')
    today = timezone.now().astimezone(eastern).date()
    
    # Get all events for the list section
    now = timezone.now()
    all_events = Event.objects.filter(
        models.Q(date__gt=now.date()) | 
        (models.Q(date=now.date()) & models.Q(end_time__gt=now.time())),
        status='active'
    )

    if filter_adult == 'false':
        all_events = all_events.exclude(age_restriction__in=['adult', 'mature'])

    # Apply search filter
    if search_query:
        all_events = all_events.filter(
            models.Q(title__icontains=search_query) |
            models.Q(description__icontains=search_query) |
            models.Q(city__icontains=search_query) |
            models.Q(group__name__icontains=search_query)
        )

    # Apply state filter
    if state_filter:
        all_events = all_events.filter(state__iexact=state_filter)

    # Get user location from form or session
    user_location = request.GET.get('user_location') or request.session.get('user_location', 'CA')
    if user_location:
        request.session['user_location'] = user_location
    
    # Apply mileage filter using OpenStreetMap geocoding
    if mileage_range and mileage_range != 'all':
        try:
            mileage = int(mileage_range)
            
            # Get user coordinates from session
            user_lat = request.session.get('user_lat')
            user_lng = request.session.get('user_lng')
            
            if user_lat and user_lng:
                # Use OpenStreetMap to calculate distances to event cities
                import requests
                import math
                
                def calculate_distance(lat1, lon1, lat2, lon2):
                    """Calculate distance between two points using Haversine formula"""
                    R = 3959  # Earth's radius in miles
                    
                    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
                    dlat = lat2 - lat1
                    dlon = lon2 - lon1
                    
                    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
                    c = 2 * math.asin(math.sqrt(a))
                    distance = R * c
                    
                    return distance
                
                def geocode_city(city, state):
                    """Geocode a city using OpenStreetMap Nominatim API"""
                    try:
                        query = f"{city}, {state}, USA"
                        url = "https://nominatim.openstreetmap.org/search"
                        params = {
                            'q': query,
                            'format': 'json',
                            'limit': 1,
                            'countrycodes': 'us'
                        }
                        headers = {
                            'User-Agent': 'FURsvp/1.0 (https://fursvp.org)'
                        }
                        
                        response = requests.get(url, params=params, headers=headers, timeout=5)
                        if response.status_code == 200:
                            data = response.json()
                            if data:
                                return float(data[0]['lat']), float(data[0]['lon'])
                    except Exception as e:
                        print(f"Geocoding error for {city}, {state}: {e}")
                    return None, None
                
                # Filter events by distance
                events_within_range = []
                user_lat, user_lng = float(user_lat), float(user_lng)
                
                for event in all_events:
                    if event.city and event.state:
                        # Try to get coordinates for the event city
                        event_lat, event_lng = geocode_city(event.city, event.state)
                        
                        if event_lat and event_lng:
                            # Calculate distance
                            distance = calculate_distance(user_lat, user_lng, event_lat, event_lng)
                            
                            if distance <= mileage:
                                events_within_range.append(event.id)
                        else:
                            # Fallback: include events in the same state for local searches
                            if mileage <= 50:
                                user_state = request.session.get('user_state', user_location)
                                if event.state == user_state:
                                    events_within_range.append(event.id)
                
                # Filter the queryset to only include events within range
                if events_within_range:
                    all_events = all_events.filter(id__in=events_within_range)
                else:
                    # If no events found, show events in the same state
                    user_state = request.session.get('user_state', user_location)
                    all_events = all_events.filter(state__iexact=user_state)
            else:
                # Fallback to state-based filtering if no coordinates
                if mileage <= 100:
                    all_events = all_events.filter(state__iexact=user_location)
                
        except ValueError:
            pass

    all_events = all_events.annotate(
        confirmed_count=models.Count('rsvps', filter=models.Q(rsvps__status='confirmed'))
    )
    
    # Add user's RSVP information if user is authenticated
    if request.user.is_authenticated:
        all_events = all_events.annotate(
            user_rsvp_status=models.Subquery(
                RSVP.objects.filter(
                    event=models.OuterRef('pk'),
                    user=request.user
                ).values('status')[:1]
            )
        )
        
        # Add user's RSVP list for template compatibility
        for event in all_events:
            user_rsvp = event.rsvps.filter(user=request.user).first()
            if user_rsvp:
                event.user_rsvp_list = [user_rsvp]
            else:
                event.user_rsvp_list = []
    
    # Apply sorting
    if sort_by == 'date':
        all_events = all_events.order_by('date', 'start_time') if sort_order == 'asc' else all_events.order_by('-date', '-start_time')
    elif sort_by == 'group':
        all_events = all_events.order_by(models.functions.Lower('group__name') if sort_order == 'asc' else models.functions.Lower('group__name').desc())
    elif sort_by == 'title':
        all_events = all_events.order_by(models.functions.Lower('title') if sort_order == 'asc' else models.functions.Lower('title').desc())
    elif sort_by == 'rsvps':
        all_events = all_events.annotate(rsvp_count=models.Count('rsvps')).order_by(
            'rsvp_count' if sort_order == 'asc' else '-rsvp_count'
        )
    
    # Pagination
    paginator = Paginator(all_events, 20)  # Show 20 events per page for expanded view
    try:
        events_page = paginator.page(page)
    except PageNotAnInteger:
        events_page = paginator.page(1)
    except EmptyPage:
        events_page = paginator.page(paginator.num_pages)
    
    # Add user's RSVP information if user is authenticated (AFTER pagination)
    if request.user.is_authenticated:
        # Add user's RSVP list for template compatibility
        for event in events_page:
            user_rsvp = event.rsvps.filter(user=request.user).first()
            if user_rsvp:
                event.user_rsvp_list = [user_rsvp]
            else:
                event.user_rsvp_list = []
    
    # Get all unique states for the dropdown
    all_states = Event.objects.exclude(state__isnull=True).exclude(state__exact='').values_list('state', flat=True).distinct().order_by('state')
    
    context = {
        'calendar': cal,
        'month_name': month_name,
        'year': year,
        'month': month,
        'events_by_date': events_by_date,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'today': today,
        'events': events_page,
        'current_sort': sort_by,
        'current_order': sort_order,
        'filter_adult': filter_adult,
        'view_type': view_type,
        'paginator': paginator,
        'page_obj': events_page,
        'all_states': all_states,
        'mileage_range': mileage_range,
        'search_query': search_query,
        'state_filter': state_filter,
    }
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # If it's an AJAX request, only return the partial event list HTML
        return render(request, 'events/events_list_partial.html', context)
    
    return render(request, 'events/event_index.html', context)

@csrf_exempt
def save_user_location(request):
    """Save user's geolocation coordinates"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lat = data.get('lat')
            lng = data.get('lng')
            state = data.get('state')
            
            if lat and lng:
                request.session['user_lat'] = lat
                request.session['user_lng'] = lng
                if state:
                    request.session['user_state'] = state
                
                return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})



@login_required
def rsvp_answers(request, event_id, user_id):
    from .models import RSVP, Event
    event = Event.objects.get(pk=event_id)
    is_organizer = (request.user == event.organizer) or request.user.is_superuser
    if not is_organizer:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    try:
        rsvp = RSVP.objects.get(event=event, user_id=user_id)
        data = {
            'question1_text': event.question1_text,
            'question1': rsvp.question1,
            'question2_text': event.question2_text,
            'question2': rsvp.question2,
            'question3_text': event.question3_text,
            'question3': rsvp.question3,
        }
        return JsonResponse(data)
    except RSVP.DoesNotExist:
        return JsonResponse({'error': 'RSVP not found'}, status=404)

@csrf_exempt
def telegram_bot_webhook(request):
    if request.method != 'POST':
        return JsonResponse({'ok': True})
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'})
    message = data.get('message', {})
    chat = message.get('chat', {})
    chat_id = str(chat.get('id'))
    text = message.get('text', '')

    from django.utils import timezone
    today = timezone.now().date()

    def send_telegram_message(chat_id, text, parse_mode=None, reply_markup=None):
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup
        resp = requests.post(url, json=payload)
        print(resp.text)

    # Try to find a group for this chat_id
    group = Group.objects.filter(telegram_webhook_channel=chat_id).first()

    # Get Telegram username if available
    username = None
    if 'from' in message and message['from'].get('username'):
        username = message['from']['username']
    elif 'callback_query' in data and data['callback_query']['from'].get('username'):
        username = data['callback_query']['from']['username']

    # Handle callback queries for RSVP list, show all groups, and RSVP menu/actions
    if "callback_query" in data:
        callback = data["callback_query"]
        chat_id = callback["message"]["chat"]["id"]
        data_str = callback["data"]
        from events.models import RSVP
        from users.models import Profile
        # Show all groups
        if data_str == "show_all_groups":
            events = Event.objects.filter(date__gte=today).order_by('date')[:10]
            msg = "<b>Upcoming Events (All Groups)</b>\n\n"
            keyboard = []
            if events:
                for event in events:
                    url = f"https://{request.get_host()}{event.get_absolute_url()}"
                    keyboard.append([
                        {"text": event.title, "callback_data": f"rsvplist_{event.id}"},
                        {"text": "RSVP", "callback_data": f"rsvp_menu_{event.id}"}
                    ])
                    msg += f"• <a href='{url}'>{event.title}</a> — <code>{event.date.strftime('%m/%d/%Y')}</code>\n"
            else:
                msg += "No events found."
            send_telegram_message(chat_id, msg, parse_mode="HTML", reply_markup={"inline_keyboard": keyboard})
            return JsonResponse({'ok': True})
        # RSVP menu
        if data_str.startswith("rsvp_menu_"):
            event_id = data_str.split("_", 2)[2]
            try:
                event = Event.objects.get(id=event_id, date__gte=today)
            except Event.DoesNotExist:
                send_telegram_message(chat_id, "Event not found.")
                return JsonResponse({'ok': True})
            # Find user by Telegram username
            user = None
            if username:
                try:
                    profile = Profile.objects.get(telegram_username=username)
                    user = profile.user
                except Profile.DoesNotExist:
                    pass
            # Check if user already RSVP'd
            existing_rsvp = RSVP.objects.filter(event=event, user=user).first() if user else None
            # Check if event is full
            confirmed_count = RSVP.objects.filter(event=event, status='confirmed').count()
            is_full = event.capacity is not None and confirmed_count >= event.capacity
            # Build RSVP options
            keyboard = []
            keyboard.append([
                {"text": "✅ Confirm", "callback_data": f"rsvp_confirm_{event.id}"},
                {"text": "❔ Maybe", "callback_data": f"rsvp_maybe_{event.id}"},
                {"text": "🚫 Not Attending", "callback_data": f"rsvp_no_{event.id}"}
            ])
            if is_full and event.waitlist_enabled:
                keyboard.append([{"text": "⏳ Waitlist", "callback_data": f"rsvp_waitlist_{event.id}"}])
            if existing_rsvp:
                keyboard.append([{"text": "Remove RSVP", "callback_data": f"rsvp_remove_{event.id}"}])
            send_telegram_message(chat_id, f"<b>Choose your RSVP status for</b> <i>{event.title}</i>", parse_mode="HTML", reply_markup={"inline_keyboard": keyboard})
            return JsonResponse({'ok': True})
        # RSVP actions
        for status in ["confirm", "maybe", "no", "waitlist", "remove"]:
            if data_str.startswith(f"rsvp_{status}_"):
                event_id = data_str.split("_", 2)[2]
                try:
                    event = Event.objects.get(id=event_id, date__gte=today)
                except Event.DoesNotExist:
                    send_telegram_message(chat_id, "Event not found.")
                    return JsonResponse({'ok': True})
                # Find user by Telegram username
                user = None
                if username:
                    try:
                        profile = Profile.objects.get(telegram_username=username)
                        user = profile.user
                    except Profile.DoesNotExist:
                        send_telegram_message(chat_id, "You must link your Telegram username in your FURsvp profile to RSVP.")
                        return JsonResponse({'ok': True})
                if not user:
                    send_telegram_message(chat_id, "You must link your Telegram username in your FURsvp profile to RSVP.")
                    return JsonResponse({'ok': True})
                if status == "remove":
                    deleted, _ = RSVP.objects.filter(event=event, user=user).delete()
                    if deleted:
                        send_telegram_message(chat_id, "Your RSVP has been removed.")
                    else:
                        send_telegram_message(chat_id, "You do not have an RSVP for this event.")
                    return JsonResponse({'ok': True})
                # Set RSVP status
                rsvp, created = RSVP.objects.get_or_create(event=event, user=user, defaults={'status': status if status != 'no' else 'not_attending'})
                if not created:
                    if status == 'waitlist':
                        rsvp.status = 'waitlisted'
                    elif status == 'maybe':
                        rsvp.status = 'maybe'
                    elif status == 'no':
                        rsvp.status = 'not_attending'
                    else:
                        rsvp.status = 'confirmed'
                    rsvp.save()
                send_telegram_message(chat_id, f"Your RSVP status for <b>{event.title}</b> is now <b>{'Waitlisted' if status == 'waitlist' else status.capitalize() if status != 'no' else 'Not Attending'}</b>.", parse_mode="HTML")
                return JsonResponse({'ok': True})
        # RSVP list (unchanged)
        if data_str.startswith("rsvplist_"):
            event_id = data_str.split("_", 1)[1]
            if group:
                event = Event.objects.filter(id=event_id, group=group, date__gte=today).first()
            else:
                event = Event.objects.filter(id=event_id, date__gte=today).first()
            if not event:
                send_telegram_message(chat_id, "Event not found.")
            else:
                show_all = bool(group)
                if not show_all and not event.attendee_list_public:
                    send_telegram_message(chat_id, "The group organizer has hidden RSVPs from the public view.")
                else:
                    rsvps = RSVP.objects.filter(event=event, status='confirmed')
                    names = [r.user.profile.get_display_name() if r.user and hasattr(r.user, 'profile') else (r.user.username if r.user else r.name or 'Anonymous') for r in rsvps]
                    if names:
                        msg = f"<b>RSVP'd Users for</b> <i>{event.title}</i>\n\n" + "\n".join([f"• {name}" for name in names])
                    else:
                        msg = f"<b>RSVP'd Users for</b> <i>{event.title}</i>\n\n<em>No RSVPs yet.</em>"
                    send_telegram_message(chat_id, msg, parse_mode="HTML")
            return JsonResponse({'ok': True})

    if text.startswith('/event'):
        parts = text.split()
        if len(parts) == 1:
            # List upcoming events for this group if found, else all
            if group:
                events = Event.objects.filter(group=group, date__gte=today).order_by('date')[:10]
            else:
                events = Event.objects.filter(date__gte=today).order_by('date')[:10]
            msg = "<b>Upcoming Events</b>\n\n"
            keyboard = []
            if events:
                for event in events:
                    url = f"https://{request.get_host()}{event.get_absolute_url()}"
                    keyboard.append([
                        {"text": event.title, "callback_data": f"rsvplist_{event.id}"},
                        {"text": "RSVP", "callback_data": f"rsvp_menu_{event.id}"}
                    ])
                    msg += f"• <a href='{url}'>{event.title}</a> — <code>{event.date.strftime('%m/%d/%Y')}</code>\n"
            else:
                msg += "No events found for this group."
            # Always add the Show All Groups button if in a group
            if group:
                keyboard.append([{"text": "Show All Groups", "callback_data": "show_all_groups"}])
            reply_markup = {"inline_keyboard": keyboard}
            send_telegram_message(chat_id, msg, parse_mode="HTML", reply_markup=reply_markup)
        else:
            event_id = parts[1]
            if group:
                event = Event.objects.filter(id=event_id, group=group, date__gte=today).first()
            else:
                event = Event.objects.filter(id=event_id, date__gte=today).first()
            if not event:
                send_telegram_message(chat_id, "No event found.")
            else:
                url = f"https://{request.get_host()}{event.get_absolute_url()}"
                msg = f"<b>{event.title}</b>\nDate: <code>{event.date.strftime('%m/%d/%Y')}</code>\n<a href='{url}'>View Event</a>\n\n{event.description or ''}"
                send_telegram_message(chat_id, msg, parse_mode="HTML")

    return JsonResponse({'ok': True})

# RSVP by Telegram username endpoint
@require_GET
@ensure_csrf_cookie
def rsvp_telegram(request, event_id):
    username = request.GET.get('username')
    if not username:
        return HttpResponse('Missing Telegram username.', status=400)
    try:
        profile = Profile.objects.get(telegram_username=username)
    except Profile.DoesNotExist:
        return HttpResponse('No user with that Telegram username is registered.', status=404)
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return HttpResponse('Event not found.', status=404)
    from events.models import RSVP
    rsvp, created = RSVP.objects.get_or_create(event=event, user=profile.user, defaults={'status': 'confirmed'})
    if not created:
        return HttpResponse('You have already RSVP\'d to this event.', status=200)
    return HttpResponse('RSVP successful! You are now confirmed for this event.', status=200)

def blog(request):
    profile = request.GET.get('profile', 'fursvp.org')
    bluesky_feed = get_bluesky_feed(profile=profile, limit=10)
    context = {
        'bluesky_feed': bluesky_feed,
        'bluesky_profile': profile,
    }
    return render(request, 'events/blog.html', context)