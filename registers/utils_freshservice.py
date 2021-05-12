from django.conf import settings
import requests


HEADERS_JSON = {'Content-Type': 'application/json'}
FRESHSERVICE_AUTH = (settings.FRESHSERVICE_API_KEY, 'X')


def get_freshservice_object(obj_type, id):
    """Query the Freshservice v2 API for a single object.
    """
    url =  '{}/{}/{}'.format(settings.FRESHSERVICE_ENDPOINT, obj_type, id)
    resp = requests.get(url, auth=FRESHSERVICE_AUTH)
    resp.raise_for_status()
    return resp.json()


def get_freshservice_objects(obj_type, query=None, verbose=False):
    """Query the Freshservice v2 API for objects of a defined type.
    ``query`` should be a valid query filter string for the API.
    """
    url =  '{}/{}'.format(settings.FRESHSERVICE_ENDPOINT, obj_type)
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
