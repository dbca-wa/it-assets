from django.core.management.base import BaseCommand
import logging
from organisation.models import DepartmentUser, ADAction


class Command(BaseCommand):
    help = 'Checks all non-completed AD actions and deletes those no longer required'

    def handle(self, *args, **options):
        logger = logging.getLogger('organisation')
        logger.info('Checking all non-completed AD actions')
        user_pks = ADAction.objects.filter(completed__isnull=True).values_list('department_user', flat=True).distinct()

        for user in DepartmentUser.objects.filter(pk__in=user_pks):
            user.audit_ad_actions()

        logger.info('Completed')
