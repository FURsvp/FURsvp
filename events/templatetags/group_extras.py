from django import template
from django.utils.safestring import mark_safe
import html

register = template.Library()

@register.simple_tag
def group_logo_src(group):
    """
    Returns the src attribute for a group logo image tag.
    If the group has a logo_base64, returns the data URL.
    Otherwise, returns None.
    """
    if group and group.logo_base64:
        # Ensure the base64 data has the proper data URL format
        if not group.logo_base64.startswith('data:'):
            # Assume it's just base64 data, add the data URL prefix
            return f"data:image/png;base64,{group.logo_base64}"
        return group.logo_base64
    return None

@register.simple_tag
def group_logo_img(group, css_class='', alt_text=None):
    """
    Returns a complete img tag for a group logo.
    If the group has a logo_base64, returns the img tag with the data URL.
    Otherwise, returns an empty string.
    """
    if group and group.logo_base64:
        src = group_logo_src(group)
        alt = alt_text or f"{group.name} logo"
        return mark_safe(f'<img src="{src}" alt="{alt}" class="{css_class}">')
    return ''

@register.filter
def decode_html_entities(text):
    """Decode HTML entities like &amp; to &"""
    if text:
        return html.unescape(text)
    return text 