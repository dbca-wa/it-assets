from django.conf import settings
from django.core.management.base import BaseCommand
import logging
from organisation.ascender import ascender_user_import_all
from sentry_sdk.crons import monitor


class Command(BaseCommand):
    help = "Caches data from Ascender on DepartmentUser objects, optionally create new M365 accounts"

    def handle(self, *args, **options):
        logger = logging.getLogger("organisation")
        logger.info("Running Ascender database import")
        # Optionally run this management command in the context of a Sentry cron monitor.
        if settings.SENTRY_CRON_CHECK_ASCENDER:
            with monitor(monitor_slug=settings.SENTRY_CRON_CHECK_ASCENDER):
                ascender_user_import_all()
        else:
            ascender_user_import_all()
