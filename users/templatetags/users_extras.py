from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def get_avatar_sized_html(profile, size):
    return profile.get_avatar_html(size=size)

@register.filter
def get_avatar_from_data(user_id, avatar_data):
    """Get avatar HTML using pre-loaded avatar data"""
    if not avatar_data or user_id not in avatar_data:
        return '<div class="rounded-circle d-flex align-items-center justify-content-center" style="width: 40px; height: 40px; background-color: #667eea; color: white; font-weight: bold;">U</div>'
    
    data = avatar_data[user_id]
    if data['has_pfp'] and data['avatar']:
        return f'<img src="{data["avatar"]}" alt="Profile" class="rounded-circle" style="width: 40px; height: 40px; object-fit: cover;">'
    else:
        return f'<div class="rounded-circle d-flex align-items-center justify-content-center" style="width: 40px; height: 40px; background-color: {data["color"]}; color: white; font-weight: bold;">{data["initials"]}</div>'

@register.inclusion_tag('users/verified_checkmark.html')
def verified_checkmark(user, size="16px"):
    """Returns a verified checkmark icon if user is staff/admin"""
    return {
        'is_staff': user.is_superuser,
        'size': size
    }

@register.filter
def has_2fa(user):
    """Returns True if user has 2FA enabled"""
    from django_otp.plugins.otp_totp.models import TOTPDevice
    return TOTPDevice.objects.filter(user=user, confirmed=True).exists() 