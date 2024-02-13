from datetime import datetime, timezone
from django.conf import settings
from django.core.management.base import BaseCommand
import logging
from organisation.models import DepartmentUser
from organisation.utils import get_blob_json
from sentry_sdk.crons import monitor


class Command(BaseCommand):
    help = 'Checks user accounts from onprem AD and links DepartmentUser objects (no creation)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--container',
            action='store',
            dest='container',
            required=True,
            help='Azure container name'
        )
        parser.add_argument(
            '--path',
            action='store',
            dest='path',
            required=True,
            help='JSON output file path'
        )

    def handle(self, *args, **options):
        logger = logging.getLogger('organisation')
        logger.info('Downloading on-prem AD user account data')
        container = options['container']
        blob = options['path']
        # Optionally run this management command in the context of a Sentry cron monitor.
        if settings.SENTRY_CRON_CHECK_ONPREM:
            with monitor(monitor_slug=settings.SENTRY_CRON_CHECK_ONPREM):
                self.check_onprem_accounts(logger, container, blob)
        else:
            self.check_onprem_accounts(logger, container, blob)

    def check_onprem_accounts(self, logger, container, blob):
        """Separate the body of this management command to allow running it in context with
        the Sentry monitor process.
        """
        ad_users = get_blob_json(container=container, blob=blob)

        if not ad_users:
            logger.error('No on-prem AD user account data could be downloaded')
            return

        logger.info('Comparing Department Users to on-prem AD user accounts')
        for ad in ad_users:
            # Only AD accounts which have an email address.
            if 'EmailAddress' in ad and ad['EmailAddress']:
                if '-admin' in ad['EmailAddress']:  # Skip admin users.
                    continue
                if not DepartmentUser.objects.filter(ad_guid=ad['ObjectGUID']).exists():
                    # No current link to this onprem AD user; try to find a match by email and link it.
                    if DepartmentUser.objects.filter(ad_guid__isnull=True, email__istartswith=ad['EmailAddress']).exists():
                        du = DepartmentUser.objects.get(email=ad['EmailAddress'].lower())
                        du.ad_guid = ad['ObjectGUID']
                        du.ad_data = ad
                        du.ad_data_updated = datetime.now(timezone.utc)
                        du.save()
                        logger.info(f"Linked existing department user {du} with onprem AD object {ad['ObjectGUID']}")
                else:
                    # An existing department user is linked to this onprem AD user.
                    du = DepartmentUser.objects.get(ad_guid=ad['ObjectGUID'])
                    du.ad_data = ad
                    du.ad_data_updated = datetime.now(timezone.utc)
                    du.save()

        logger.info('Completed')
