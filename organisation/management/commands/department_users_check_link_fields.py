from datetime import datetime, timezone
from django.core.management.base import BaseCommand
import logging

from organisation.ascender import ascender_employee_fetch
from organisation.models import DepartmentUser
from organisation.utils import ms_graph_users, get_ad_users_json


class Command(BaseCommand):
    help = 'Checks DepartmentUser objects and clears any linking fields that are no longer valid'

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
            help='Onprem AD users JSON file path'
        )

    def handle(self, *args, **options):
        logger = logging.getLogger('organisation')

        logger.info('Querying Microsoft Graph API for Azure AD user accounts')
        azure_users = ms_graph_users()

        if not azure_users:
            logger.error('Microsoft Graph API returned no data')
            return

        azure_users = {i['objectId']: i for i in azure_users}

        # Iterate through department users and clear any nonexistent Azure AD GUID values.
        logger.info('Comparing department users to Azure AD user accounts')
        for du in DepartmentUser.objects.filter(azure_guid__isnull=False):
            if du.azure_guid not in azure_users:
                logger.info(f"Azure AD GUID {du.azure_guid} not found in MS Graph output; clearing it from {du}")
                du.active = False
                du.azure_guid = None
                du.azure_ad_data = {}
                du.azure_ad_data_updated = datetime.now(timezone.utc)
                du.assigned_licences = []
                du.dir_sync_enabled = None
                du.save()

        logger.info('Downloading on-prem AD user account data')
        ad_users = get_ad_users_json(container=options['container'], azure_json_path=options['path'])
        ad_users = {i['ObjectGUID']: i for i in ad_users}

        # Iterate through department users and clear any nonexistent onprem GUID values.
        logger.info('Comparing department users to Azure AD user accounts')
        for du in DepartmentUser.objects.filter(ad_guid__isnull=False):
            if du.ad_guid not in ad_users:
                logger.info(f"On-premise AD GUID {du.ad_guid} not found in onprem AD output; clearing it from {du}")
                du.ad_guid = None
                du.ad_data = {}
                du.ad_data_updated = datetime.now(timezone.utc)
                du.username = None
                du.save()

        logger.info('Downloading Ascender user account data')
        employee_iter = ascender_employee_fetch()
        employee_ids = []
        for eid, jobs in employee_iter:
            employee_ids.append(eid)

        # Iterate through department users and clear any nonexistent onprem GUID values.
        logger.info('Comparing department users to Ascender employee IDs')
        for du in DepartmentUser.objects.filter(employee_id__isnull=False):
            if du.ad_guid not in ad_users:
                logger.info(f"Employee ID {du.employee_id} not found in Ascender; clearing it from {du}")
                du.employee_id = None
                du.ascender_data = {}
                du.ascender_data_updated = datetime.now(timezone.utc)
                du.save()

        # Iterate through department users and clear any managers who are inactive.
        for du in DepartmentUser.objects.filter(manager__isnull=False):
            if not du.manager.active:
                logger.info(f"Manager {du.manager} is inactive; clearing them from {du}")
                du.manager = None
                du.save()
