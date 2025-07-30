from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'events'
    
    def ready(self):
        import events.signals
        
        # Initialize platform stats on startup
        try:
            from .signals import initialize_platform_stats
            initialize_platform_stats()
        except Exception:
            # Silently fail if database isn't ready yet
            pass