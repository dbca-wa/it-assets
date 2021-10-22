from django.core.management.base import BaseCommand
from datetime import date, timedelta
import logging
from status.models import HostStatus


class Command(BaseCommand):
    help = 'Deletes host status objects older than n days (default 90)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, action='store', dest='days', default=90,
            help='Delete HostStatus objects older than this value of days (integer)')

    def handle(self, *args, **options):
        if options['days']:
            d = date.today() - timedelta(days=options['days'])
        else:
            d = date.today() - timedelta(days=90)

        old_statuses = HostStatus.objects.filter(date__lt=d)
        logger = logging.getLogger('status')
        logger.info('Deleting {} old HostStatus objects'.format(old_statuses.count()))
        old_statuses.delete()
