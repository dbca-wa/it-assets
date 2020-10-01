import traceback
import logging

from django.core.management.base import BaseCommand

from nginx import log_harvester

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Harvest nginx configuration from blob storage'

    def handle(self, *args, **options):
        try:
            log_harvester.harvest()
        except :
            logger.error(traceback.format_exc())

