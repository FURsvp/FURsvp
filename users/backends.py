import hashlib
import hmac
import time
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from django.conf import settings
from .models import Profile, BannedUser


class TelegramBackend(BaseBackend):
    """
    Custom authentication backend for Telegram Login Widget
    """
    
    def authenticate(self, request, telegram_data=None):
        if not telegram_data:
            return None
            
        # Validate Telegram data
        if not self._validate_telegram_data(telegram_data):
            return None
            
        telegram_id = telegram_data.get('id')
        username = telegram_data.get('username')
        first_name = telegram_data.get('first_name', '')
        last_name = telegram_data.get('last_name', '')
        
        if not telegram_id:
            return None
            
        # Try to find existing user by Telegram ID
        try:
            profile = Profile.objects.get(telegram_id=telegram_id)
            user = profile.user
            
            # Check if user is site-wide banned
            if BannedUser.objects.filter(user=user, group__isnull=True).exists():
                return None  # Prevent login for banned users
                
            return user
        except Profile.DoesNotExist:
            # Create new user if Telegram ID doesn't exist
            return self._create_user_from_telegram(telegram_data)
    
    def _validate_telegram_data(self, telegram_data):
        """
        Validate Telegram data using hash verification
        """
        try:
            # Get the hash from the data
            received_hash = telegram_data.get('hash')
            if not received_hash:
                return False
                
            # Remove hash from data for validation
            data_check_string = '\n'.join([
                f"{k}={v}" for k, v in sorted(telegram_data.items()) 
                if k != 'hash'
            ])
            
            # Create secret key from bot token
            secret_key = hmac.new(
                b"WebAppData",
                settings.TELEGRAM_BOT_TOKEN.encode(),
                hashlib.sha256
            ).digest()
            
            # Calculate hash
            calculated_hash = hmac.new(
                secret_key,
                data_check_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Check if hash is valid
            if calculated_hash != received_hash:
                return False
                
            # Check if data is not too old (within 24 hours)
            auth_date = int(telegram_data.get('auth_date', 0))
            if time.time() - auth_date > 86400:  # 24 hours
                return False
                
            return True
            
        except Exception:
            return False
    
    def _create_user_from_telegram(self, telegram_data):
        """
        Create a new user from Telegram data
        """
        telegram_id = telegram_data.get('id')
        username = telegram_data.get('username')
        first_name = telegram_data.get('first_name', '')
        last_name = telegram_data.get('last_name', '')
        
        # Generate unique username if Telegram username is taken
        base_username = username or f"telegram_{telegram_id}"
        username = base_username
        counter = 1
        
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email='',  # Telegram doesn't provide email
            first_name=first_name,
            last_name=last_name,
            password=None  # No password for Telegram users
        )
        
        # Create profile with Telegram data
        profile = Profile.objects.create(
            user=user,
            telegram_id=int(telegram_id),
            telegram_username=telegram_data.get('username'),
            display_name=f"{first_name} {last_name}".strip() or username
        )
        
        return user
    
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None 