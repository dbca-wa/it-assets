from django.core.management.base import BaseCommand
import logging
from organisation.ascender import employee_ids_audit


class Command(BaseCommand):
    help = 'Checks the set of Ascender employee ID values on DepartmentUser objects and removes invalid ones'

    def handle(self, *args, **options):
        logger = logging.getLogger('organisation')
        logger.info('Checking currently-recorded employee ID values for department users')
        employee_ids_audit()
