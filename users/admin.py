from django.contrib import admin
from .models import Profile, GroupRole, AuditLog
from events.models import Group

class GroupRoleInline(admin.TabularInline):
    model = GroupRole
    extra = 1

class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'display_name', 'discord_username', 'telegram_username', 'telegram_id')
    search_fields = ('user__username', 'user__email', 'display_name', 'discord_username', 'telegram_username')
    fields = ('user', 'display_name', 'discord_username', 'telegram_username', 'telegram_id', 'profile_picture_base64', 'can_post_blog')
    readonly_fields = ('user',)

admin.site.register(Profile, ProfileAdmin)

class GroupAdmin(admin.ModelAdmin):
    inlines = [GroupRoleInline]
    list_display = ('name', 'description', 'website', 'contact_email', 'telegram_channel')

admin.site.unregister(Group)
admin.site.register(Group, GroupAdmin)

from django.contrib.auth.models import User
class UserAdmin(admin.ModelAdmin):
    inlines = [GroupRoleInline]
    list_display = ('username', 'email', 'is_staff', 'is_superuser')

admin.site.unregister(User)
admin.site.register(User, UserAdmin)

class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'target_user', 'group', 'event', 'timestamp', 'ip_address')
    list_filter = ('action', 'timestamp', 'group', 'event')
    search_fields = ('user__username', 'target_user__username', 'description', 'group__name', 'event__title')
    readonly_fields = ('user', 'action', 'description', 'target_user', 'group', 'event', 'ip_address', 'user_agent', 'timestamp', 'additional_data')
    ordering = ('-timestamp',)
    list_per_page = 50
    
    def has_add_permission(self, request):
        return False  # Prevent manual creation of audit logs
    
    def has_change_permission(self, request, obj=None):
        return False  # Prevent editing of audit logs
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superusers can delete audit logs

admin.site.register(AuditLog, AuditLogAdmin) 