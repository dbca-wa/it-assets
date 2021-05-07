from django.db.models import Q
from django.utils.encoding import smart_text
from django.utils.text import smart_split
from functools import reduce
import os
import requests


def smart_truncate(content, length=100, suffix='....(more)'):
    """Small function to truncate a string in a sensible way, sourced from:
    http://stackoverflow.com/questions/250357/smart-truncate-in-python
    """
    content = smart_text(content)
    if len(content) <= length:
        return content
    else:
        return ' '.join(content[:length + 1].split(' ')[0:-1]) + suffix


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


def sharepoint_access_token():
    """Query the Sharepoint REST API for a dict containing an access token.
    """
    tenant_id = os.environ["SHAREPOINT_TENANT_ID"]
    client_id = os.environ["SHAREPOINT_CLIENT_ID"]
    client_secret = os.environ["SHAREPOINT_CLIENT_SECRET"]

    # Get an access token for further requests.
    token_url = "https://accounts.accesscontrol.windows.net/{}/tokens/OAuth/2".format(tenant_id)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    params = {
        "grant_type": "client_credentials",
        "resource": "00000003-0000-0ff1-ce00-000000000000/dpaw.sharepoint.com@{}".format(tenant_id),
        "client_id": "{}@{}".format(client_id, tenant_id),
        "client_secret": client_secret,
    }
    return requests.post(token_url, params, headers=headers).json()


def sharepoint_user_information_list():
    """Query Sharepoint for details of all users in our tenancy.
    """
    token_resp = sharepoint_access_token()

    # Get the User Information List details (we need the GUID).
    url = "https://dpaw.sharepoint.com/_api/web/lists"
    headers = {
        "Accept": "application/json;odata=verbose",
        "Authorization": "{} {}".format(token_resp["token_type"], token_resp["access_token"])
    }
    resp_json = requests.get(url, headers=headers).json()
    lists = resp_json['d']['results']
    for l in lists:
        if l['Title'] == 'User Information List':
            uil = l
            break

    # Get the list of users.
    url = "https://dpaw.sharepoint.com/_api/web/lists(guid'{}')/items".format(uil['Id'])
    users = []
    more_users = True

    while more_users:
        resp_json = requests.get(url, headers=headers).json()
        users += resp_json['d']['results']
        if '__next' in resp_json['d']:
            url = resp_json['d']['__next']
        else:
            more_users = False

    return users


def sharepoint_it_system_register_list():
    """Query Sharepoint for the IT System Register list contents.
    """
    token_resp = sharepoint_access_token()

    # Get the IT Systems Register list details (we need the GUID).
    url = "https://dpaw.sharepoint.com/Divisions/corporate/oim/_api/Web/lists"
    headers = {
        "Accept": "application/json;odata=verbose",
        "Authorization": "{} {}".format(token_resp["token_type"], token_resp["access_token"])
    }
    resp_json = requests.get(url, headers=headers).json()
    lists = resp_json['d']['results']
    for l in lists:
        if l['Title'] == 'IT Systems Register':
            register_list = l
            break

    # IT System register
    url = "https://dpaw.sharepoint.com/Divisions/corporate/oim/_api/Web/lists(guid'{}')/items".format(register_list['Id'])
    it_systems = []
    more_systems = True

    while more_systems:
        resp_json = requests.get(url, headers=headers).json()
        it_systems += resp_json['d']['results']
        if '__next' in resp_json['d']:
            url = resp_json['d']['__next']
        else:
            more_systems = False

    return it_systems
