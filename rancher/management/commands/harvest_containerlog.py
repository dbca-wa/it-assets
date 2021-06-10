import traceback
import logging

from django.core.management.base import BaseCommand

from rancher import containerlog_harvester

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Harvest container log from blob storage'

    def handle(self, *args, **options):
        try:
            context = {}
            containerlog_harvester.harvest_all(context)
        except :
            logger.error(traceback.format_exc())

