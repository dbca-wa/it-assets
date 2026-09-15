import logging
from datetime import date

from django.core.management.base import BaseCommand
from django.conf import settings

from organisation.models import DepartmentUser

class Command(BaseCommand):
    help = ""

    def handle(self, *args, **options):
        logger = logging.getLogger("organisation")
        logger.info("")
        users = DepartmentUser.objects.all().exclude(term_date_data__iexact="[]") # All users with termination date records

        terminated_account_days = settings.TERMINATED_ACCOUNT_DAYS
        today = date.today()

        for user in users:
            pass