from datetime import datetime, timezone
from django.core.management.base import BaseCommand
import logging

from organisation.models import DepartmentUser, CostCentre, Location
from organisation.utils import ms_graph_users


class Command(BaseCommand):
    help = 'Checks licensed user accounts from Azure AD and updates linked DepartmentUser objects'

    def handle(self, *args, **options):
        logger = logging.getLogger('organisation')
        logger.info('Querying Microsoft Graph API for Azure AD user accounts')
        azure_users = ms_graph_users()

        if not azure_users:
            logger.error('Microsoft Graph API returned no data')
            return

        logger.info('Comparing Department Users to Azure AD user accounts')
        for az in azure_users:
            if az['mail'] and az['displayName']:  # Azure object has an email address and a display name; proceed.
                if DepartmentUser.objects.filter(azure_guid=az['objectId']).exists():
                    # An existing DepartmentUser is linked to this Azure AD user.
                    # Update the existing DepartmentUser object fields with values from Azure.
                    existing_user = DepartmentUser.objects.get(azure_guid=az['objectId'])
                    existing_user.azure_ad_data = az
                    existing_user.azure_ad_data_updated = datetime.now(timezone.utc)
                    existing_user.update_from_azure_ad_data()
