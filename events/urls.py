from django.urls import path
from . import views
from .views import manage_group_leadership, telegram_bot_webhook, rsvp_telegram, blog

urlpatterns = [
    path('', views.home, name='home'),
    path('calendar/', views.event_calendar, name='event_calendar'),
    path('event/<int:event_id>/', views.event_detail, name='event_detail'),
    path('event/<int:event_id>/edit/', views.edit_event, name='edit_event'),
    path('event/<int:event_id>/uncancel/', views.uncancel_event, name='uncancel_event'),
    path('create-event/', views.create_event, name='create_event'),
    path('group/<int:group_id>/', views.group_detail, name='group_detail'),
    path('terms/', views.terms, name='terms'),
    path('faq/', views.faq, name='faq'),
    path('eula/', views.eula, name='eula'),
    path('privacy/', views.privacy, name='privacy'),
    path('group/<int:group_id>/leadership/', manage_group_leadership, name='manage_group_leadership'),
    path('group/', views.groups_list, name='groups_list'),
    path('event/<int:event_id>/rsvp_answers/<int:user_id>/', views.rsvp_answers, name='rsvp_answers'),
    path('telegram/bot/', telegram_bot_webhook, name='telegram_bot_webhook'),
    path('event/<int:event_id>/rsvp_telegram/', rsvp_telegram, name='rsvp_telegram'),
    path('blog/', blog, name='blog'),
    path('event/<int:event_id>/organizer-tools/', views.organizer_tools, name='organizer_tools'),
    path('event/<int:event_id>/export-csv/', views.export_attendees_csv, name='export_attendees_csv'),
    path('event/<int:event_id>/generate-badges/', views.generate_badges, name='generate_badges'),
    path('event/<int:event_id>/generate-checkin-sheet/', views.generate_checkin_sheet, name='generate_checkin_sheet'),
    path('event/<int:event_id>/rsvp/<int:rsvp_id>/update-badge-settings/', views.update_badge_settings, name='update_badge_settings'),
    path('event/<int:event_id>/checkin/<int:rsvp_id>/', views.checkin_attendee, name='checkin_attendee'),
] 