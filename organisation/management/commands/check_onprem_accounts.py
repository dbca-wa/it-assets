from datetime import datetime, timezone
from django.core.management.base import BaseCommand
import logging
from organisation.models import DepartmentUser
from organisation.utils import get_ad_users_json


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
        ad_users = get_ad_users_json(container=options['container'], blob=options['path'])

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
