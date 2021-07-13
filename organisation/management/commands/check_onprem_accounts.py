from django.core.management.base import BaseCommand
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
            '--json_path',
            action='store',
            dest='json_path',
            required=True,
            help='JSON output file path'
        )

    def handle(self, *args, **options):
        self.stdout.write('Downloading on-prem AD user account data')
        ad_users = get_ad_users_json(container=options['container'], azure_json_path=options['json_path'])

        if not ad_users:
            self.stdout.write(self.style.ERROR('No on-prem AD user account data could be downloaded'))
            return

        self.stdout.write('Comparing Department Users to on-prem AD user accounts')
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
                        du.save()
                        du.update_deptuser_from_onprem_ad()
                        self.stdout.write(
                            self.style.SUCCESS('Linked existing department user {} with onprem AD object {}'.format(du, ad['ObjectGUID']))
                        )
                else:
                    # An existing department user is linked to this onprem AD user.
                    du = DepartmentUser.objects.get(ad_guid=ad['ObjectGUID'])
                    du.ad_data = ad
                    du.save()
                    du.update_deptuser_from_onprem_ad()

        self.stdout.write(self.style.SUCCESS('Completed'))
