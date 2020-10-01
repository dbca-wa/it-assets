import traceback
import logging

from django.core.management.base import BaseCommand

from rancher import rancher_harvester

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Harvest nginx configuration from blob storage'

    def handle(self, *args, **options):
        try:
            rancher_harvester.harvest_all()
        except :
            logger.error(traceback.format_exc())

