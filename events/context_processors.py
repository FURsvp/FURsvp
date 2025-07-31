from django.db import models
from django.utils import timezone
from .models import Event, Group, PlatformStats
from django.contrib.auth.models import User
from .models import RSVP
from users.models import GroupRole

def global_stats(request):
    """Provide global statistics for templates"""
    try:
        # Get cumulative stats that always increase
        stats = PlatformStats.get_or_create_stats()
        
        # Get current time for filtering active events
        now = timezone.now()
        
        # Active events (current and future)
        active_events = Event.objects.filter(
            models.Q(date__gte=now.date()) | 
            (models.Q(date=now.date()) & models.Q(end_time__gt=now.time())),
            status='active'
        ).count()
        
        return {
            'global_events_count': stats.total_events_created,
            'global_groups_count': stats.total_groups_created,
            'global_users_count': stats.total_users_registered,
            'global_rsvps_count': stats.total_rsvps_created,
            'active_events_count': active_events,
        }
    except Exception:
        # Return default values if there's any database error
        return {
            'global_events_count': 0,
            'global_groups_count': 0,
            'global_users_count': 0,
            'global_rsvps_count': 0,
            'active_events_count': 0,
        }

def user_groups(request):
    """Provide user's groups for navigation"""
    if request.user.is_authenticated:
        try:
            # Get groups where user is a leader
            user_groups = GroupRole.objects.filter(user=request.user).select_related('group').order_by('group__name')
            groups_list = [role.group for role in user_groups]
                        
            # Force refresh by checking the database directly
            from django.db import connection
            connection.ensure_connection()
            
            return {
                'user_groups': groups_list,
                'user_groups_count': len(groups_list),
                'user_groups_timestamp': timezone.now().timestamp(),  # Cache busting
            }
        except Exception as e:
            return {
                'user_groups': [],
                'user_groups_count': 0,
            }
    else:
        return {
            'user_groups': [],
            'user_groups_count': 0,
        } 