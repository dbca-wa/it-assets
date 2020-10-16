from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from bigpicture import utils


class Command(BaseCommand):
    help = 'Extracts the Signal Science feed for the previous hour and upload it to Azure container'

    def handle(self, *args, **options):
        from_time = datetime.utcnow().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        self.stdout.write('Extracting Signal Sciences feed starting from {}'.format(from_time.isoformat()))
        filename = utils.signal_sciences_write_feed()
        if filename:
            self.stdout.write(self.style.SUCCESS('{} uploaded to Azure container'.format(filename)))
        else:
            self.stdout.write(self.style.ERROR('Upload failed'))
