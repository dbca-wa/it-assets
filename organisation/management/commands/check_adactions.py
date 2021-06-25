from django.core.management.base import BaseCommand
from organisation.models import DepartmentUser, ADAction


class Command(BaseCommand):
    help = 'Checks all non-completed AD actions and deletes those no longer required'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Checking all non-completed AD actions'))
        user_pks = ADAction.objects.filter(completed__isnull=True).values_list('department_user', flat=True).distinct()

        for user in DepartmentUser.objects.filter(pk__in=user_pks):
            user.audit_ad_actions()

        self.stdout.write(self.style.SUCCESS('Completed'))
