from django.core.management.base import BaseCommand
from tracking.utils_salt import salt_load_computers


class Command(BaseCommand):
    help = 'Loads data from Salt (minions/grains).'

    def handle(self, *args, **options):
        salt_load_computers()
