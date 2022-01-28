from datetime import datetime, timezone
from django.core.management.base import BaseCommand
import logging
from multiprocessing import Process, Queue

from organisation.models import DepartmentUser, CostCentre, Location
from organisation.utils import ms_graph_users


def get_users(queue):
    # Worker function to call the Graph API via a process queue.
    azure_users = queue.get()
    azure_users = ms_graph_users()
    queue.put(azure_users)
    return


class Command(BaseCommand):
    help = 'Checks licensed user accounts from Azure AD and creates/updates linked DepartmentUser objects'

    def handle(self, *args, **options):
        logger = logging.getLogger('organisation')
        logger.info('Querying Microsoft Graph API for Azure AD user accounts')

        # Call the MS Graph API in a separate process with a timeout.
        azure_users = None
        queue = Queue()
        queue.put(azure_users)
        process = Process(target=get_users, args=(queue,))
        process.start()
        process.join(timeout=80)  # Give this function a maximum time to finish (process will block for this duration, regardless).
        logger.info('Completed')
        azure_users = queue.get()

        if not process.exitcode == 0:
            logger.error('Queued process did not complete in time')
            return

        if not azure_users:
            logger.error('Microsoft Graph API returned no data')
            return

        logger.info('Comparing Department Users to Azure AD user accounts')
        for az in azure_users:
            if az['mail'] and az['displayName']:  # Azure object has an email address and a display name; proceed.
                if not DepartmentUser.objects.filter(azure_guid=az['objectId']).exists():
                    # No existing DepartmentUser is linked to this Azure AD user.

                    # A department user with matching email may already exist in IT Assets with a different azure_guid.
                    # If so, return a warning and skip that user.
                    # We'll need to correct this issue manually.
                    if DepartmentUser.objects.filter(email=az['mail'], azure_guid__isnull=False).exists():
                        existing_user = DepartmentUser.objects.filter(email=az['mail']).first()
                        logger.warning(
                            'Skipped {}: email exists and already associated with Azure ObjectId {} (this ObjectId is {})'.format(az['mail'], existing_user.azure_guid, az['objectId'])
                        )
                        continue  # Skip to the next Azure user.

                    # A department user with matching email may already exist in IT Assets with no azure_guid.
                    # If so, associate the Azure AD objectId with that user.
                    if DepartmentUser.objects.filter(email=az['mail'], azure_guid__isnull=True).exists():
                        existing_user = DepartmentUser.objects.filter(email=az['mail']).first()
                        existing_user.azure_guid = az['objectId']
                        existing_user.azure_ad_data = az
                        existing_user.azure_ad_data_updated = datetime.now(timezone.utc)
                        existing_user.update_from_azure_ad_data()
                        logger.info('AZURE AD SYNC: linked existing user {} with Azure objectId {}'.format(az['mail'], az['objectId']))
                        continue  # Skip to the next Azure user.

                    # Only create a new DepartmentUser instance if the Azure AD account has >0 licences assigned to it.
                    if az['assignedLicenses']:
                        if az['companyName'] and CostCentre.objects.filter(code=az['companyName']).exists():
                            cost_centre = CostCentre.objects.get(code=az['companyName'])
                        else:
                            cost_centre = None

                        if az['officeLocation'] and Location.objects.filter(name=az['officeLocation']).exists():
                            location = Location.objects.get(name=az['officeLocation'])
                        else:
                            location = None

                        new_user = DepartmentUser.objects.create(
                            azure_guid=az['objectId'],
                            azure_ad_data=az,
                            azure_ad_data_updated=datetime.now(timezone.utc),
                            active=az['accountEnabled'],
                            email=az['mail'],
                            name=az['displayName'],
                            given_name=az['givenName'],
                            surname=az['surname'],
                            title=az['jobTitle'],
                            telephone=az['telephoneNumber'],
                            mobile_phone=az['mobilePhone'],
                            cost_centre=cost_centre,
                            location=location,
                            dir_sync_enabled=az['onPremisesSyncEnabled'],
                        )
                        logger.info(f'AZURE AD SYNC: created new department user {new_user}')
                else:
                    # An existing DepartmentUser is linked to this Azure AD user.
                    # Update the existing DepartmentUser object fields with values from Azure.
                    existing_user = DepartmentUser.objects.get(azure_guid=az['objectId'])
                    existing_user.azure_ad_data = az
                    existing_user.azure_ad_data_updated = datetime.now(timezone.utc)
                    existing_user.update_from_azure_ad_data()

        # Iterate through department users and clear any nonexistent Azure AD GUID values.
        azure_users = {i['objectId']: i for i in azure_users}
        for du in DepartmentUser.objects.filter(azure_guid__isnull=False, email__iendswith='@dbca.wa.gov.au'):
            if du.azure_guid not in azure_users:
                logger.info("ONPREM AD SYNC: Azure AD GUID {} not found in MS Graph output; clearing it from {}".format(du.azure_guid, du))
                du.azure_guid = None
                du.azure_ad_data = {}
                du.azure_ad_data_updated = datetime.now(timezone.utc)
                du.assigned_licences = []
                du.dir_sync_enabled = None
                du.save()

        logger.info('Completed')
