from django.core.management.base import BaseCommand
import logging
from itassets.utils import ms_graph_client_token
from organisation.models import DepartmentUser


class Command(BaseCommand):
    help = 'Caches data from Ascender on matching DepartmentUser objects'

    def add_arguments(self, parser):
        parser.add_argument(
            '--log-only',
            action='store_true',
            help='Log changes only',
            dest='log_only',
        )

    def handle(self, *args, **options):
        logger = logging.getLogger('organisation')
        logger.info('Checking department users for required changes to sync to AD')
        token = ms_graph_client_token()

        for du in DepartmentUser.objects.filter():
            du.sync_ad_data(log_only=options['log_only'], token=token)
