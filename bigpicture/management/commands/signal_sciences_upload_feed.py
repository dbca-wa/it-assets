from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from bigpicture import utils


class Command(BaseCommand):
    help = '''Extracts the Signal Science feed for the defined duration and upload it to Azure blob storage.
    Defaults to querying the most-recent 15 minutes of data (offset by a 5 minute delay).
    Optionally also records a summary of tags to CSV and uploads to blob storage.
    '''

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes-ago', action='store', dest='min_ago', type=int, default=20,
            help='Extract feed from this many minutes in the past (integer, optional)')
        parser.add_argument(
            '--duration', action='store', dest='duration', type=int, default=15,
            help='Extract feed for this many minutes duration (integer, optional)')
        parser.add_argument(
            '--compress', action='store', dest='compress', type=bool, default=False,
            help='Compress the uploaded feed using gzip (boolean, optional)')
        parser.add_argument(
            '--csv', action='store', dest='csv', type=bool, default=False,
            help='Summarise tags to CSV and upload to Azure (boolean, optional)')

    def handle(self, *args, **options):
        from_datetime = datetime.utcnow().replace(second=0, microsecond=0) - timedelta(minutes=options['min_ago'])
        self.stdout.write('Extracting Signal Sciences feed starting from {}, duration {} minutes'.format(from_datetime.isoformat(), options['duration']))
        filename = utils.signal_sciences_upload_feed(
            from_datetime=from_datetime,
            minutes=options['duration'],
            compress=options['compress'],
            csv=options['csv']
        )
        if filename:
            self.stdout.write(self.style.SUCCESS('{} uploaded to Azure container'.format(filename)))
        else:
            self.stdout.write(self.style.ERROR('Feed querying and upload failed'))
