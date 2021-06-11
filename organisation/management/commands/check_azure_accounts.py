from django.core.management.base import BaseCommand
from organisation.models import DepartmentUser, CostCentre, Location
from organisation.utils import ms_graph_users, update_deptuser_from_azure


class Command(BaseCommand):
    help = 'Checks user accounts from Azure AD and creates/updates linked DepartmentUser objects'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Comparing Department Users to licensed Azure AD user accounts'))
        azure_users = ms_graph_users(licensed=True)

        for az in azure_users:
            if not DepartmentUser.objects.filter(azure_guid=az['objectId']).exists():
                if az['mail']:  # Azure object has an email address; proceed.

                    # A department user with matching email may already exist in IT Assets with a different azure_guid.
                    # If so, return a warning and skip that user.
                    if DepartmentUser.objects.filter(email__istartswith=az['mail'], azure_guid__isnull=False).exists():
                        existing_user = DepartmentUser.objects.filter(email__istartswith=az['mail']).first()
                        self.stdout.write(
                            self.style.NOTICE(
                                'Skipped {}: email exists and already associated with Azure ObjectId {} (this ObjectId is {})'.format(az['mail'], existing_user.azure_guid, az['objectId'])
                            )
                        )
                        continue

                    # A department user with matching email may already exist in IT Assets with no azure_guid.
                    # If so, simply associate the Azure AD objectId with that user.
                    if DepartmentUser.objects.filter(email__istartswith=az['mail'], azure_guid__isnull=True).exists():
                        existing_user = DepartmentUser.objects.filter(email__istartswith=az['mail']).first()
                        existing_user.azure_guid = az['objectId']
                        existing_user.save()
                        self.stdout.write(
                            self.style.WARNING('Updated existing user {} with Azure objectId {}'.format(az['mail'], az['objectId']))
                        )
                        continue

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
                    update_deptuser_from_azure(az, new_user)  # Easier way to set some fields.
                    self.stdout.write(self.style.SUCCESS('Created {}'.format(new_user.email)))
            else:
                if az['mail']:  # Azure object has an email; proceed.
                    # Update the existing DepartmentUser object fields with values from Azure.
                    user = DepartmentUser.objects.get(azure_guid=az['objectId'])
                    try:
                        update_deptuser_from_azure(az, user)
                    except:
                        self.stdout.write(
                            self.style.NOTICE(
                                'Error during sync of {} with Azure objectId {}'.format(user.email, az['objectId'])
                            )
                        )

        self.stdout.write(self.style.SUCCESS('Completed'))
