from django.core.management.base import BaseCommand

from accounts.commands.load_adhered_pharmacies import load_adhered_pharmacies


class Command(BaseCommand):
    help = 'Loads adhered Rafaela pharmacies that are not already stored.'

    def handle(self, *args, **options):  # noqa: ARG002
        result = load_adhered_pharmacies()
        self.stdout.write(f'Created {len(result.created)} pharmacies.')
        if result.already_loaded:
            self.stdout.write(f'Already loaded: {len(result.already_loaded)}.')
