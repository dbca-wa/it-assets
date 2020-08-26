from django.core.management.base import BaseCommand
from organisation.models import DepartmentUser, ADAction
from organisation.utils import get_azure_users_json, find_user_in_list


class Command(BaseCommand):
    help = 'Checks all non-completed AD actions and deletes those no longer required'

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
        self.stdout.write(self.style.SUCCESS('Checking all non-completed AD actions'))
        ad_users = get_azure_users_json(container=options['container'], azure_json_path=options['json_path'])
        user_pks = ADAction.objects.filter(completed__isnull=True).values_list('department_user', flat=True).distinct()

        for user in DepartmentUser.objects.filter(pk__in=user_pks):
            azure_user = find_user_in_list(ad_users, user.email)
            if azure_user:
                user.audit_ad_actions(azure_user)

        self.stdout.write(self.style.SUCCESS('Completed'))
