from django.core.management.base import BaseCommand
import logging
from organisation.utils import ms_graph_site_storage_summary


class Command(BaseCommand):
    help = 'Generates a CSV containing SharePoint site storage usage and uploads it to blob storage'

    def handle(self, *args, **options):
        logger = logging.getLogger('organisation')
        logger.info('Generating CSV of SharePoint site storage usage and uploading to blob storage')
        ms_graph_site_storage_summary()
        logger.info('Completed')
