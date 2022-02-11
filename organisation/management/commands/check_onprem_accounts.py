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
        ad_users = get_ad_users_json(container=options['container'], azure_json_path=options['path'])

        if not ad_users:
            logger.error('No on-prem AD user account data could be downloaded')
            return

        logger.info('Comparing Department Users to on-prem AD user accounts')
        for ad in ad_users:
            # Only check enabled (active) AD accounts which have an email address.
            if 'Enabled' in ad and ad['Enabled'] and 'EmailAddress' in ad and ad['EmailAddress']:
                if '-admin' in ad['EmailAddress']:  # Skip admin users.
                    continue
                if not DepartmentUser.objects.filter(ad_guid=ad['ObjectGUID']).exists():
                    # No current link to this onprem AD user; try to find a match by email and link it.
                    if DepartmentUser.objects.filter(ad_guid__isnull=True, email__istartswith=ad['EmailAddress']).exists():
                        du = DepartmentUser.objects.get(email=ad['EmailAddress'].lower())
                        du.ad_guid = ad['ObjectGUID']
                        du.ad_data = ad
                        du.ad_data_updated = datetime.now(timezone.utc)
                        du.update_from_onprem_ad_data()
                        logger.info('ONPREM AD SYNC: linked existing department user {} with onprem AD object {}'.format(du, ad['ObjectGUID']))
                else:
                    # An existing department user is linked to this onprem AD user.
                    du = DepartmentUser.objects.get(ad_guid=ad['ObjectGUID'])
                    du.ad_data = ad
                    du.ad_data_updated = datetime.now(timezone.utc)
                    du.update_from_onprem_ad_data()

        # Iterate through department users and clear any nonexistent onprem GUID values.
        ad_users = {i['ObjectGUID']: i for i in ad_users}
        for du in DepartmentUser.objects.filter(ad_guid__isnull=False):
            if du.ad_guid not in ad_users:
                logger.info("ONPREM AD SYNC: onprem AD GUID {} not found in onprem AD output; clearing it from {}".format(du.ad_guid, du))
                du.ad_guid = None
                du.ad_data = {}
                du.ad_data_updated = datetime.now(timezone.utc)
                du.username = None
                du.save()
