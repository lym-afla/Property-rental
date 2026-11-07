from django.core.management.base import BaseCommand, CommandError

from rentals.services.fx_client import FXClient
from rentals.services.fx_mirror import sync


class Command(BaseCommand):
    help = 'Synchronize the shared FX mirror.'

    def handle(self, *args, **options):
        try:
            state = sync(FXClient())
        except Exception as exc:
            raise CommandError('FX synchronization failed') from exc
        self.stdout.write(f'FX mirror synchronized at sequence {state.seq}')
