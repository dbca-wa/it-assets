from django.core.management.base import BaseCommand
from organisation.models import DepartmentUser, CostCentre, Location
from organisation.utils import get_azure_users_json, update_deptuser_from_azure


class Command(BaseCommand):
    help = 'Checks user accounts from Azure AD and creates new linked DepartmentUser objects as needed'

    def add_arguments(self, parser):
        parser.add_argument(
            '--container',
            action='store',
            dest='container',
            required=True,
            help='Azure container name'
        )
        parser.add_argument(
            '--json_path',
            action='store',
            dest='json_path',
            required=True,
            help='JSON output file path'
        )

    def handle(self, *args, **options):
        azure_users = get_azure_users_json(container=options['container'], azure_json_path=options['json_path'])

        for az in azure_users:
            if not DepartmentUser.objects.filter(azure_guid=az['ObjectId']).exists():
                if az['Mail'] and az['AssignedLicenses']:  # Azure object has an email and is licensed; create it.

                    if az['Manager'] and DepartmentUser.objects.filter(azure_guid=az['Manager']['ObjectId']).exists():
                        manager = DepartmentUser.objects.get(azure_guid=az['Manager']['ObjectId'])
                    else:
                        manager = None

                    if az['CompanyName'] and CostCentre.objects.filter(code=az['CompanyName']).exists():
                        cost_centre = CostCentre.objects.get(code=az['CompanyName'])
                    else:
                        cost_centre = None

                    if az['PhysicalDeliveryOfficeName'] and Location.objects.filter(name=az['PhysicalDeliveryOfficeName']).exists():
                        location = Location.objects.get(name=az['PhysicalDeliveryOfficeName'])
                    else:
                        location = None

                    new_user = DepartmentUser.objects.create(
                        azure_guid=az['ObjectId'],
                        active=az['AccountEnabled'],
                        email=az['Mail'],
                        name=az['DisplayName'],
                        given_name=az['GivenName'],
                        surname=az['Surname'],
                        title=az['JobTitle'],
                        telephone=az['TelephoneNumber'],
                        mobile_phone=az['Mobile'],
                        manager=manager,
                        cost_centre=cost_centre,
                        location=location,
                        mail_nickname=az['MailNickName'],
                        dir_sync_enabled=az['DirSyncEnabled'],
                    )
                    update_deptuser_from_azure(az, new_user)  # Easier way to set some fields.
                    self.stdout.write('CREATED: {}'.format(new_user.email))
