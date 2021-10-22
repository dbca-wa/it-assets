from django.core.management.base import BaseCommand
import logging
from status.utils import run_all


class Command(BaseCommand):
    help = 'Runs a full scan of all plugins in the status application'

    def handle(self, *args, **options):
        logger = logging.getLogger('status')
        logger.info('Running a full scan')
        run_all()
        logger.info('Completed')
