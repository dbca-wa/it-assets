from django.core.management.base import BaseCommand
import logging
from organisation.ascender import update_cc_managers


class Command(BaseCommand):
    help = "Queries data from Ascender to update Cost Centre managers"

    def handle(self, *args, **options):
        logger = logging.getLogger("organisation")
        logger.info("Querying Ascender database for cost centre manager information")
        update_cc_managers()
