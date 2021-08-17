import traceback
import logging
import re

from django.core.management.base import BaseCommand

from rancher import rancher_harvester

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Harvest rancher configuration from blob storage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reconsume', action='store_true', dest='reconsume', default=False,
            help='reconsume all files or not.')

        parser.add_argument(
            '--file-filter', action='store', dest='file_filter', default=None,
            help='The file filter.')


    def handle(self, *args, **options):
        try:
            if options["file_filter"]:
                rancher_harvester.RANCHER_FILE_RE=re.compile(options["file_filter"])
                
            rancher_harvester.harvest_all(reconsume=options["reconsume"])
        except :
            logger.error(traceback.format_exc())

