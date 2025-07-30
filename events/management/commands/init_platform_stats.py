from django.core.management.base import BaseCommand
from events.models import PlatformStats


class Command(BaseCommand):
    help = 'Initialize platform statistics with current data'

    def handle(self, *args, **options):
        self.stdout.write('Initializing platform statistics...')
        
        try:
            # Sync stats with current data
            stats = PlatformStats.sync_with_current_data()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully initialized platform statistics:\n'
                    f'  Total Events Created: {stats.total_events_created}\n'
                    f'  Total RSVPs Created: {stats.total_rsvps_created}\n'
                    f'  Total Users Registered: {stats.total_users_registered}\n'
                    f'  Total Groups Created: {stats.total_groups_created}\n'
                    f'  Last Updated: {stats.last_updated}'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error initializing platform statistics: {e}')
            ) 