from django.core.management.base import BaseCommand
from django.conf import settings
import json
import logging
import requests
from tracking import utils_freshdesk

LOGGER = logging.getLogger('sync_tasks')


class Command(BaseCommand):
    help = 'Download and cache recent Freshdesk tickets.'

    def add_arguments(self, parser):
        # Named (optional) arguments:
        parser.add_argument(
            '-l',
            '--limit',
            action='store',
            dest='limit',
            default=0,  # No limit.
            type=int,
            help='Maximum number of tickets to download and cache.',
        )

    def handle(self, *args, **options):
        # Begin by caching Agents as Contacts.
        utils_freshdesk.freshdesk_cache_agents()
        # Next, start caching tickets one page at a time.
        url = settings.FRESHDESK_ENDPOINT + '/tickets'
        # By default, the 'list tickets' API returns tickets created in the
        # past 30 days only. If older tickets need to be cached, modify the
        # params dict below to include a value for "updated_since".
        # Ref: https://developer.freshdesk.com/api/#list_all_tickets
        params = {'page': 1, 'per_page': 100}
        further_results = True
        cached_count = 0

        while further_results:
            if options['limit'] and (cached_count + params['per_page']) >= options['limit']:
                params['per_page'] = options['limit'] - cached_count
            r = requests.get(url, auth=(settings.FRESHDESK_API_KEY, 'X'), params=params)
            LOGGER.info(json.dumps(dict(r.headers)))
            # If we've been rate-limited, response status will be 429.
            if r.status_code == 429:
                print('Rate limit reached; terminating.')
                further_results = False
            elif r.status_code == 200:
                if 'link' not in r.headers:  # No further paginated results.
                    further_results = False
                else:
                    params['page'] += 1
                tickets = r.json()
                cache = utils_freshdesk.freshdesk_cache_tickets(tickets)
                if not cache:  # Error!
                    further_results = False
                cached_count += len(tickets)
                if options['limit'] and cached_count >= options['limit']:
                    further_results = False
            else:
                further_results = False
