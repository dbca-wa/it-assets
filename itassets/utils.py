from azure.storage.blob import BlobServiceClient
from io import BytesIO
from django.conf import settings
from django.db.models import Q
from django.utils.encoding import smart_str
import json
from msal import ConfidentialClientApplication
import os
import re
import requests


FRESHSERVICE_AUTH = (settings.FRESHSERVICE_API_KEY, 'X')


def ms_graph_client_token():
    """Uses the Microsoft msal library to obtain an access token for the Graph API.
    Ref: https://docs.microsoft.com/en-us/python/api/msal/msal.application.confidentialclientapplication
    """
    azure_tenant_id = os.environ["AZURE_TENANT_ID"]
    client_id = os.environ["MS_GRAPH_API_CLIENT_ID"]
    client_secret = os.environ["MS_GRAPH_API_CLIENT_SECRET"]
    context = ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority="https://login.microsoftonline.com/{}".format(azure_tenant_id),
    )
    token = context.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

    return token


def ms_security_api_client_token():
    """Calls the Microsoft 365 Defender API endpoint to obtain an access token.
    Ref: https://docs.microsoft.com/en-us/microsoft-365/security/defender/api-hello-world
    """
    azure_tenant_id = os.environ["AZURE_TENANT_ID"]
    client_id = os.environ["MS_GRAPH_API_CLIENT_ID"]
    client_secret = os.environ["MS_GRAPH_API_CLIENT_SECRET"]
    data = {
        'resource': 'https://api.security.microsoft.com',
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials',
    }
    url = "https://login.windows.net/{}/oauth2/token".format(azure_tenant_id)
    resp = requests.post(url, data=data)
    return resp.json()['access_token']


def upload_blob(in_file, container, blob, overwrite=True):
    """For the passed-in file, upload to blob storage.
    """
    connect_string = os.environ.get('AZURE_CONNECTION_STRING')
    service_client = BlobServiceClient.from_connection_string(connect_string)
    blob_client = service_client.get_blob_client(container=container, blob=blob)
    blob_client.upload_blob(in_file, overwrite=overwrite)


def download_blob(out_file, container, blob):
    """For the passed-in file, download the nominated blob into it.
    """
    connect_string = os.environ.get('AZURE_CONNECTION_STRING')
    service_client = BlobServiceClient.from_connection_string(connect_string)
    container_client = service_client.get_container_client(container=container)
    out_file.write(container_client.download_blob(blob).readall())
    out_file.flush()
    out_file.seek(0)

    return out_file


class ModelDescMixin(object):
    """A small mixin for the ModelAdmin class to add a description of the model to the
    admin changelist view context.

    In order to then display this description above the list view, you then need to
    override the relevant change_list.html template.
    """

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        if hasattr(self, "model_description"):
            extra_context["model_description"] = self.model_description
        return super().changelist_view(request, extra_context=extra_context)


def breadcrumbs_list(links):
    """Returns a list of links to render as breadcrumbs inside a <ul> element in a HTML template.
    ``links`` should be a iterable of tuples (URL, text).
    """
    crumbs = ""
    li_str = '<li class="breadcrumb-item"><a href="{}">{}</a></li>'
    li_str_active = '<li class="breadcrumb-item active"><span>{}</span></li>'
    # Iterate over the list, except for the last item.
    if len(links) > 1:
        for i in links[:-1]:
            crumbs += li_str.format(i[0], i[1])
    # Add the final "active" item.
    crumbs += li_str_active.format(links[-1][1])
    return crumbs


def get_query(query_string, search_fields):
    """Returns a query which is a combination of Q objects. That combination
    aims to search keywords within a model by testing the given search fields.

    Splits the query string into individual keywords, getting rid of unecessary
    spaces and grouping quoted words together.
    """
    findterms = re.compile(r'"([^"]+)"|(\S+)').findall
    normspace = re.compile(r"\s{2,}").sub
    query = None  # Query to search for every search term
    terms = [normspace(" ", (t[0] or t[1]).strip()) for t in findterms(query_string)]
    for term in terms:
        or_query = None  # Query to search for a given term in each field
        for field_name in search_fields:
            q = Q(**{"%s__icontains" % field_name: term})
            if or_query is None:
                or_query = q
            else:
                or_query = or_query | q
        if query is None:
            query = or_query
        else:
            query = query & or_query
    return query


TIME_DURATION_UNITS = (
    ('week', 60 * 60 * 24 * 7),
    ('day', 60 * 60 * 24),
    ('hour', 60 * 60),
    ('minute', 60),
    ('second', 1)
)


def human_time_duration(seconds: int) -> str:
    """For a passed-in integer (seconds), return a human-readable duration string.
    """
    if seconds <= 1:
        return '<1 second'
    parts = []
    for unit, div in TIME_DURATION_UNITS:
        amount, seconds = divmod(int(seconds), div)
        if amount > 0:
            parts.append('{} {}{}'.format(amount, unit, "" if amount == 1 else "s"))
    return ', '.join(parts)


def humanise_bytes(bytes: int) -> str:
    """For a passed-in integer (bytes), return a human-readable string.
    """
    for x in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if bytes < 1024.0:
            return "{:3.1f} {}".format(bytes, x)
        bytes /= 1024.0


def smart_truncate(content, length=100, suffix='....(more)'):
    """Small function to truncate a string in a sensible way, sourced from:
    http://stackoverflow.com/questions/250357/smart-truncate-in-python
    """
    content = smart_str(content)
    if len(content) <= length:
        return content
    else:
        return ' '.join(content[:length + 1].split(' ')[0:-1]) + suffix


def get_blob_json(container, blob):
    """Convenience function to download an Azure blob which contains JSON data,
    parse it, and return the data. Pass in the container and blob names.
    """
    tf = BytesIO()
    download_blob(tf, container, blob)
    tf.flush()

    return json.loads(tf.read())


def get_previous_pages(page_num, count=3):
    """Convenience function to take a Paginator page object and return the previous `count`
    page numbers, to a minimum of 1.
    """
    prev_page_numbers = []

    if page_num and page_num.has_previous():
        for i in range(page_num.previous_page_number(), page_num.previous_page_number() - count, -1):
            if i >= 1:
                prev_page_numbers.append(i)

    prev_page_numbers.reverse()
    return prev_page_numbers


def get_next_pages(page_num, count=3):
    """Convenience function to take a Paginator page object and return the next `count`
    page numbers, to a maximum of the paginator page count.
    """
    next_page_numbers = []

    if page_num and page_num.has_next():
        for i in range(page_num.next_page_number(), page_num.next_page_number() + count):
            if i <= page_num.paginator.num_pages:
                next_page_numbers.append(i)

    return next_page_numbers


def get_freshservice_objects(obj_type):
    """Query the Freshservice v2 API for objects of a defined type.
    """
    url = '{}/{}'.format(settings.FRESHSERVICE_ENDPOINT, obj_type)
    params = {
        'page': 1,
        'per_page': 100,
    }
    objects = []
    further_results = True

    while further_results:
        resp = requests.get(url, auth=FRESHSERVICE_AUTH, params=params)

        if 'link' not in resp.headers:  # No further paginated results.
            further_results = False

        objects.extend(resp.json()[obj_type])
        params['page'] += 1

    # Return the list of objects returned.
    return objects


def get_freshservice_object(obj_type, key, value):
    """Use the Freshservice v2 API to retrieve a single object.
    Accepts an object type, object attribute to use, and a value to filter on.
    Returns the first object found, or None.
    """
    objects = get_freshservice_objects(obj_type)
    return next((obj for obj in objects if obj[key] == value), None)


def create_freshservice_object(obj_type, data):
    """Use the Freshservice v2 API to create an object.
    Accepts an object name (string) and a dict of key values.
    """
    url = '{}/{}'.format(settings.FRESHSERVICE_ENDPOINT, obj_type)
    resp = requests.post(url, auth=FRESHSERVICE_AUTH, json=data)
    return resp  # Return the response, so we can handle unsuccessful responses.


def update_freshservice_object(obj_type, id, data):
    """Use the Freshservice v2 API to update an object.
    Accepts an object type name (string), object ID and a dict of key values.
    """
    url = '{}/{}/{}'.format(settings.FRESHSERVICE_ENDPOINT, obj_type, id)
    resp = requests.put(url, auth=FRESHSERVICE_AUTH, json=data)
    return resp  # Return the response, so we can handle unsuccessful responses.
