from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('register/success/', views.registration_success, name='registration_success'),
    path('pending-approval/', views.pending_approval, name='pending_approval'),
    path('login/', views.custom_login, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('profile/', views.profile, name='profile'),
    path('administration/', views.administration, name='administration'),
    path('<int:user_id>/ban/', views.ban_user, name='ban_user'),
    path('user_search_autocomplete/', views.user_search_autocomplete, name='user_search_autocomplete'),
    path('notifications/', views.get_notifications, name='get_notifications'),
    path('notifications/mark_as_read/', views.mark_notifications_as_read, name='mark_notifications_as_read'),
    path('notifications/purge_read/', views.purge_read_notifications, name='purge_read_notifications'),
    path('notifications/all/', views.notifications_page, name='notifications_page'),
    path('send_bulk_notification/', views.send_bulk_notification, name='send_bulk_notification'),
    path('send_notification/', views.send_notification, name='send_notification'),
    
    # Telegram Authentication URLs
    path('telegram/login/', views.telegram_login, name='telegram_login'),
    path('telegram/login/embedded/', views.telegram_login_embedded, name='telegram_login_embedded'),
    path('telegram/link/', views.link_telegram_account, name='link_telegram_account'),
    path('telegram/unlink/', views.unlink_telegram_account, name='unlink_telegram_account'),
    path('twofa/enable/', views.twofa_enable, name='twofa_enable'),
    path('twofa/disable/', views.twofa_disable, name='twofa_disable'),
    path('twofa/settings/', views.twofa_settings, name='twofa_settings'),
    path('post_to_bluesky/', views.post_to_bluesky, name='post_to_bluesky'),
    path('delete_bluesky_post/', views.delete_bluesky_post, name='delete_bluesky_post'),
] 