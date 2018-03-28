from django.core.management.base import BaseCommand
from django.conf import settings
import json
import requests
from time import sleep
from tracking import utils_freshdesk
from tracking.utils import logger_setup


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
        logger_headers = logger_setup('freshdesk_api_response_headers')
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
            r = requests.get(url, auth=settings.FRESHDESK_AUTH, params=params)
            logger_headers.info(json.dumps(dict(r.headers)))
            # If we've been rate-limited, response status will be 429.
            # Sleep for the number of seconds specifief by the Retry-After header.
            if r.status_code == 429:
                if 'retry-after' in r.headers:
                    naptime = r.headers['retry-after']
                else:
                    naptime = 3600  # Sleep for an hour.
                sleep(naptime)
            # If the response
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
                    print('Caching limit reached; terminating.')
                    further_results = False
            else:
                further_results = False
