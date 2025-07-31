from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def get_avatar_sized_html(profile, size):
    return profile.get_avatar_html(size=size)

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