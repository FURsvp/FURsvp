from django.core.management.base import BaseCommand
from events.models import PlatformStats


class Command(BaseCommand):
    help = 'Ensure platform statistics are properly initialized and synced'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-sync even if stats already exist',
        )

    def handle(self, *args, **options):
        self.stdout.write('Ensuring platform statistics are properly initialized...')
        
        try:
            # Get or create stats
            stats = PlatformStats.get_or_create_stats()
            
            if options['force'] or stats.total_events_created == 0:
                # Sync with current data
                stats = PlatformStats.sync_with_current_data()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Platform statistics initialized/synced:\n'
                        f'  Total Events Created: {stats.total_events_created}\n'
                        f'  Total RSVPs Created: {stats.total_rsvps_created}\n'
                        f'  Total Users Registered: {stats.total_users_registered}\n'
                        f'  Total Groups Created: {stats.total_groups_created}\n'
                        f'  Last Updated: {stats.last_updated}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Platform statistics already initialized:\n'
                        f'  Total Events Created: {stats.total_events_created}\n'
                        f'  Total RSVPs Created: {stats.total_rsvps_created}\n'
                        f'  Total Users Registered: {stats.total_users_registered}\n'
                        f'  Total Groups Created: {stats.total_groups_created}\n'
                        f'  Last Updated: {stats.last_updated}'
                    )
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error ensuring platform statistics: {e}')
            ) 