from django.core.management.base import BaseCommand
from organisation.models import DepartmentUser
from organisation.utils import get_azure_users_json, find_user_in_list, update_deptuser_from_onprem_ad


class Command(BaseCommand):
    help = 'Checks user accounts from onprem AD and links DepartmentUser objects'

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
        self.stdout.write(self.style.SUCCESS('Comparing Department Users to on-prem AD user accounts'))
        ad_users = get_azure_users_json(container=options['container'], azure_json_path=options['json_path'])

        for user in DepartmentUser.objects.filter(active=True, ad_guid__isnull=True):
            ad_user = find_user_in_list(ad_users, user.email)
            if ad_user:
                update_deptuser_from_onprem_ad(ad_user, user)
                self.stdout.write(self.style.SUCCESS('Updated ad_guid for {}'.format(user.email)))

        self.stdout.write(self.style.SUCCESS('Completed'))
