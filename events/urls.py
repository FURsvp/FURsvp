from django.urls import path
from . import views
from .views import manage_group_leadership, telegram_bot_webhook, rsvp_telegram, blog

urlpatterns = [
    path('', views.home, name='home'),
    path('events/', views.event_index, name='event_index'),
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
    path('save-location/', views.save_user_location, name='save_user_location'),
    path('blog/', blog, name='blog'),
] 