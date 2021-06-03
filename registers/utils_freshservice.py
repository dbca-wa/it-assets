from django.conf import settings
import json
from math import ceil
from subprocess import check_output
import requests


FRESHSERVICE_AUTH = (settings.FRESHSERVICE_API_KEY, 'X')


def get_freshservice_object(obj_type, id):
    """Query the Freshservice v2 API for a single object.
    """
    url = '{}/{}/{}'.format(settings.FRESHSERVICE_ENDPOINT, obj_type, id)
    resp = requests.get(url, auth=FRESHSERVICE_AUTH)
    resp.raise_for_status()
    return resp.json()


def get_freshservice_objects_curl(obj_type, query=None, verbose=False):
    """The `requests` library has a (normally very useful) feature of normalising
    quotes in request URIs (https://github.com/kennethreitz/requests/blob/master/requests/utils.py#L604).
    The Freshservice V2 API on the other hand requires that
    filter requests include query strings be enclosed in double quotes.
    Reference: https://api.freshservice.com/v2/#filter_assets
    As we can't force request to NOT requote URIs, we're forced to call on curl directly
    on the command line :(
    We very much indent to factor this method out when possible.
    """
    url = '{}/{}'.format(settings.FRESHSERVICE_ENDPOINT, obj_type)
    if query:
        url = url + '?query="{}"'.format(query)

    if verbose:
        print('Querying {}'.format(url))

    # First, make a query to get the count of results.
    out = check_output([
        'curl',
        '--silent',
        '--head',
        '--user', '{}:X'.format(settings.FRESHSERVICE_API_KEY),
        '--header', 'Content-Type: application/json',
        '--request', 'GET',
        url
    ])
    out_lines = out.decode().strip().splitlines()
    if '200 OK' not in out_lines[0]:
        print(out_lines[0])
        return None

    count = None
    for line in out_lines:
        if line.startswith('X-Search-Results-Count'):
            count = line
            break
    if not count:
        return None
    count = int(count.split()[1])
    if verbose:
        print(out_lines)

    if count == 0:
        return None

    pages = ceil(count / 30)  # Always 30 results/page for filter queries.
    objects = []

    # Starting at 1, call the API
    for i in range(1, pages + 1):
        url_page = url + '&include=type_fields&page={}'.format(i)
        if verbose:
            print('Querying page {}'.format(i))

        out = check_output([
            'curl',
            '--silent',
            '--user', '{}:X'.format(settings.FRESHSERVICE_API_KEY),
            '--header', 'Content-Type: application/json',
            '--request', 'GET',
            url_page
        ])
        resp = json.loads(out.strip())
        objects = objects + resp[obj_type]

    return objects


def get_freshservice_objects(obj_type, query=None, verbose=False):
    """Query the Freshservice v2 API for objects of a defined type.
    ``query`` should be a valid query filter string for the API.
    """
    url = '{}/{}'.format(settings.FRESHSERVICE_ENDPOINT, obj_type)
    params = {
        'page': 1,
        'include': 'type_fields',
    }
    if query:
        # Note that we can't just add the query string to params, because requests
        # helpfully URL-encodes away the double quotes.
        # The easiest solution is simply to append the query string on the URL.
        url = url + '?query="{}"'.format(query)
    objects = []
    further_results = True

    while further_results:
        if verbose:
            print('Querying page {}'.format(params['page']))

        resp = requests.get(url, auth=FRESHSERVICE_AUTH, params=params)
        resp.raise_for_status()

        if 'link' not in resp.headers:  # No further paginated results.
            further_results = False
            if verbose:
                print('Done!')

        objects.extend(resp.json()[obj_type])
        params['page'] += 1

    # Return the list of objects returned.
    return objects


def create_freshservice_object(obj_type, data):
    """Use the Freshservice v2 API to create an object.
    Accepts an object name (string) and a dict of key values.
    """
    url = '{}/{}'.format(settings.FRESHSERVICE_ENDPOINT, obj_type)
    resp = requests.post(url, auth=FRESHSERVICE_AUTH, json=data)
    resp.raise_for_status()

    return resp  # Return the response, so we can handle unsuccessful responses.


def update_freshservice_object(obj_type, id, data):
    """Use the Freshservice v2 API to create an object.
    Accepts an object name (string) and a dict of key values.
    """
    url = '{}/{}/{}'.format(settings.FRESHSERVICE_ENDPOINT, obj_type, id)
    resp = requests.put(url, auth=FRESHSERVICE_AUTH, json=data)
    resp.raise_for_status()

    return resp  # Return the response, so we can handle unsuccessful responses.
