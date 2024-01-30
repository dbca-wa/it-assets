from django.core.management.base import BaseCommand
import logging
from organisation.ascender import ascender_user_import_all


class Command(BaseCommand):
    help = 'Caches data from Ascender on DepartmentUser objects, optionally create new M365 accounts'

    def handle(self, *args, **options):
        logger = logging.getLogger('organisation')
        logger.info('Running Ascender database import')
        ascender_user_import_all()
