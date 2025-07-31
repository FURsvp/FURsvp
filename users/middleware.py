from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django.core.cache import cache
from .models import BannedUser


class BanCheckMiddleware:
    """
    Middleware to check if logged-in users are banned and log them out if necessary
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if user is authenticated
        if request.user.is_authenticated:
            # Check cache for immediate logout (recent ban)
            cache_key = f"ban_logout_{request.user.id}"
            if cache.get(cache_key):
                cache.delete(cache_key)  # Clear the cache
                
                # Log out the user immediately
                logout(request)
                messages.error(request, 'Your account has been banned from this site.')
                return redirect('login')
            
            # Check if user is site-wide banned
            if BannedUser.objects.filter(user=request.user, group__isnull=True).exists():
                # Get ban information for the message
                ban_entry = BannedUser.objects.filter(user=request.user, group__isnull=True).first()
                
                # Log out the user
                logout(request)
                
                # Add ban message
                if ban_entry and ban_entry.reason:
                    messages.error(request, f'Your account has been banned: {ban_entry.reason}')
                else:
                    messages.error(request, 'Your account has been banned from this site.')
                
                # Redirect to login page
                return redirect('login')
        
        response = self.get_response(request)
        return response 