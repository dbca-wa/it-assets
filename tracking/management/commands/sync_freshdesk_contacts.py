from django.core.management.base import BaseCommand
from tracking.utils_freshdesk import freshdesk_sync_contacts


class Command(BaseCommand):
    help = "Synchronises DepartmentUser data to Freshdesk contacts."

    def handle(self, *args, **options):
        freshdesk_sync_contacts()
