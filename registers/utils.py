from django.db.models import Q
from django.utils.text import smart_split
from functools import reduce
import requests
from itassets.utils import ms_graph_client_token


def split_text_query(query):
    """Filter stopwords, but only if there are also other words.
    """
    stopwords = '''a,am,an,and,as,at,be,by,can,did,do,for,get,got,
        had,has,he,her,him,his,how,i,if,in,is,it,its,let,may,me,
        my,no,nor,not,of,off,on,or,our,own,say,says,she,so,than,
        that,the,them,then,they,this,to,too,us,was,we,were,what,
        when,who,whom,why,will,yet,you,your'''.split(',')
    split_query = list(smart_split(query))
    filtered_query = [word for word in split_query if word not in stopwords]

    return filtered_query if len(filtered_query) else split_query


def search_filter(search_fields, query_string):
    """search_fields example: ['name', 'category__name', 'description', 'id']
    Returns a Q filter, use like so: MyModel.objects.filter(Q)
    """
    query_string = query_string.strip()
    filters = []
    null_filter = Q(pk=None)

    for word in split_text_query(query_string):
        queries = [Q(**{'{}__icontains'.format(field_name): word}) for field_name in search_fields]
        filters.append(reduce(Q.__or__, queries))

    return reduce(Q.__and__, filters) if len(filters) else null_filter


def ms_graph_sharepoint_users():
    token = ms_graph_client_token()
    if not token:
        return None

    headers = {
        "Authorization": "Bearer {}".format(token["access_token"]),
        "ConsistencyLevel": "eventual",
    }
    url = "https://graph.microsoft.com/v1.0/sites/dpaw.sharepoint.com/lists/a9a3eaf6-6580-4506-b7ac-73b621b5ab7a/items?expand=fields"
    sharepoint_users = []
    resp = requests.get(url, headers=headers)
    j = resp.json()

    while '@odata.nextLink' in j:
        sharepoint_users = sharepoint_users + j['value']
        resp = requests.get(j['@odata.nextLink'], headers=headers)
        resp.raise_for_status()
        j = resp.json()

    sharepoint_users = sharepoint_users + j['value']  # Final page
    return [user['fields'] for user in sharepoint_users]


def ms_graph_sharepoint_it_systems():
    token = ms_graph_client_token()
    if not token:
        return None

    headers = {
        "Authorization": "Bearer {}".format(token["access_token"]),
        "ConsistencyLevel": "eventual",
    }
    url = "https://graph.microsoft.com/v1.0/sites/dpaw.sharepoint.com,485537cf-e72c-431d-9d71-f5101df1f274,2091d73c-5d12-4d02-ac11-fdbe889a6d95/lists/65703834-92c6-4de6-9d10-83862730115f/items?expand=fields"
    it_systems = []
    resp = requests.get(url, headers=headers)
    j = resp.json()

    while '@odata.nextLink' in j:
        it_systems = it_systems + j['value']
        resp = requests.get(j['@odata.nextLink'], headers=headers)
        resp.raise_for_status()
        j = resp.json()

    it_systems = it_systems + j['value']
    return [system['fields'] for system in it_systems]
