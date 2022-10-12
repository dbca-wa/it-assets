from django.core.management.base import BaseCommand
import logging
from organisation.ascender import ascender_db_import


class Command(BaseCommand):
    help = 'Caches data from Ascender on matching DepartmentUser objects'

    def handle(self, *args, **options):
        logger = logging.getLogger('organisation')
        logger.info('Running Ascender database import')
        ascender_db_import()
