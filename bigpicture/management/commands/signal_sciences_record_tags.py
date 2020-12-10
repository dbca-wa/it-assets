from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
import json

from bigpicture.utils import signal_sciences_extract_feed
from nginx.models import WebApp


class Command(BaseCommand):
    help = '''Extracts the Signal Science feed for the defined duration and associates each of
    the system tags to the suitable IT System.
    Defaults to querying the most-recent 15 minutes of data (offset by a 5 minute delay).
    '''

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes-ago', action='store', dest='min_ago', type=int, default=20,
            help='Extract feed from this many minutes in the past (integer, optional)')
        parser.add_argument(
            '--duration', action='store', dest='duration', type=int, default=15,
            help='Extract feed for this many minutes duration (integer, optional)')

    def handle(self, *args, **options):
        from_datetime = datetime.utcnow().replace(second=0, microsecond=0) - timedelta(minutes=options['min_ago'])
        self.stdout.write('Querying Signal Sciences feed starting from {}'.format(from_datetime.isoformat()))
        feed_str = signal_sciences_extract_feed(from_datetime=from_datetime, minutes=options['duration'])
        if feed_str:
            self.stdout.write(self.style.SUCCESS('Feed queried successfully'))
        else:
            self.stdout.write(self.style.ERROR('Feed query failed'))

        # Iterate through the feed.
        feed_json = json.loads(feed_str)
        for obj in feed_json:
            if WebApp.objects.filter(name=obj['serverName']).exists():
                webapp = WebApp.objects.filter(name=obj['serverName']).first()
                if webapp.system_alias and webapp.system_alias.system:
                    itsystem = webapp.system_alias.system
                    if not itsystem.extra_data:
                        itsystem.extra_data = {'signal_science_tags': {}}
                    if 'signal_science_tags' not in itsystem.extra_data:
                        itsystem.extra_data['signal_science_tags'] = {}
                    for tag in obj['tags']:
                        if not tag['type'] in itsystem.extra_data['signal_science_tags']:
                            itsystem.extra_data['signal_science_tags'][tag['type']] = 1
                        else:
                            itsystem.extra_data['signal_science_tags'][tag['type']] += 1
                    itsystem.save()
                    self.stdout.write(self.style.SUCCESS('Updated Signal Sciences tags for {}'.format(itsystem)))
