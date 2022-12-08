from data_storage import AzureBlobStorage
from datetime import datetime, timedelta
from django.conf import settings
from io import BytesIO
import json
import os
import pytz
import re
import requests
import unicodecsv as csv
from itassets.utils import ms_graph_client_token

TZ = pytz.timezone(settings.TIME_ZONE)


def title_except(
    s,
    exceptions=('the', 'of', 'for', 'and', 'or'),
    acronyms=(
        'OIM', 'IT', 'PVS', 'SFM', 'OT', 'NP', 'FMDP', 'VRM', 'TEC', 'GIS', 'ODG', 'RIA', 'ICT',
        'RSD', 'CIS', 'PSB', 'FMB', 'CFO', 'BCS', 'CIO',
    ),
):
    """Utility function to title-case words in a job title, except for all the exceptions and edge cases.
    """
    words = s.split()

    if words[0].startswith('A/'):
        words_title = ['A/' + words[0].replace('A/', '').capitalize()]
    elif words[0] in acronyms:
        words_title = [words[0]]
    else:
        words_title = [words[0].capitalize()]

    for word in words[1:]:
        word = word.lower()

        if word.startswith('('):
            pre = '('
            word = word.replace('(', '')
        else:
            pre = ''

        if word.endswith(')'):
            post = ')'
            word = word.replace(')', '')
        else:
            post = ''

        if word.replace(',', '').upper() in acronyms:
            word = word.upper()
        elif word in exceptions:
            pass
        else:
            word = word.capitalize()

        words_title.append(pre + word + post)

    return ' '.join(words_title)


def ms_graph_subscribed_skus(token=None):
    """Query the Microsoft Graph REST API for a list of commercial licence subscriptions.
    To map licence names against skuId, reference:
    https://docs.microsoft.com/en-us/azure/active-directory/enterprise-users/licensing-service-plan-reference
    """
    if not token:
        token = ms_graph_client_token()
    if not token:  # The call to the MS API occassionally fails.
        return None

    headers = {
        "Authorization": "Bearer {}".format(token["access_token"]),
    }
    url = "https://graph.microsoft.com/v1.0/subscribedSkus"
    skus = []
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    j = resp.json()

    while '@odata.nextLink' in j:
        skus = skus + j['value']
        resp = requests.get(j['@odata.nextLink'], headers=headers)
        resp.raise_for_status()
        j = resp.json()

    skus = skus + j['value']  # Final page.
    return skus


def ms_graph_subscribed_sku(sku_id, token=None):
    if not token:
        token = ms_graph_client_token()
    if not token:  # The call to the MS API occassionally fails.
        return None

    headers = {
        "Authorization": "Bearer {}".format(token["access_token"]),
    }
    azure_tenant_id = os.environ["AZURE_TENANT_ID"]
    url = f"https://graph.microsoft.com/v1.0/subscribedSkus/{azure_tenant_id}_{sku_id}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def ms_graph_users(licensed=False):
    """Query the Microsoft Graph REST API for Azure AD user accounts in our tenancy.
    Passing ``licensed=True`` will return only those users having >0 licenses assigned.
    Note that accounts are filtered to return only those with email *@dbca.wa.gov.au.
    """
    token = ms_graph_client_token()
    if not token:  # The call to the MS API occassionally fails.
        return None

    headers = {
        "Authorization": "Bearer {}".format(token["access_token"]),
        "ConsistencyLevel": "eventual",
    }
    url = "https://graph.microsoft.com/v1.0/users?$select=id,mail,userPrincipalName,displayName,givenName,surname,employeeId,employeeType,jobTitle,businessPhones,mobilePhone,department,companyName,officeLocation,proxyAddresses,accountEnabled,onPremisesSyncEnabled,onPremisesSamAccountName,lastPasswordChangeDateTime,assignedLicenses&$filter=endswith(mail,'@dbca.wa.gov.au')&$count=true"
    #url = "https://graph.microsoft.com/v1.0/users?$select=id,mail,userPrincipalName,displayName,givenName,surname,employeeId,employeeType,jobTitle,businessPhones,mobilePhone,department,companyName,officeLocation,proxyAddresses,accountEnabled,onPremisesSyncEnabled,onPremisesSamAccountName,lastPasswordChangeDateTime,assignedLicenses&$filter=endswith(mail,'@dbca.wa.gov.au')&$count=true&$expand=manager($select=id,mail)"
    users = []
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    j = resp.json()

    while '@odata.nextLink' in j:
        users = users + j['value']
        resp = requests.get(j['@odata.nextLink'], headers=headers)
        resp.raise_for_status()
        j = resp.json()

    users = users + j['value']  # Final page
    aad_users = []

    for user in users:
        aad_users.append({
            'objectId': user['id'],
            'mail': user['mail'].lower(),
            'userPrincipalName': user['userPrincipalName'],
            'displayName': user['displayName'] if user['displayName'] else None,
            'givenName': user['givenName'] if user['givenName'] else None,
            'surname': user['surname'] if user['surname'] else None,
            'employeeId': user['employeeId'] if user['employeeId'] else None,
            'employeeType': user['employeeType'] if user['employeeType'] else None,
            'jobTitle': user['jobTitle'] if user['jobTitle'] else None,
            'telephoneNumber': user['businessPhones'][0] if user['businessPhones'] else None,
            'mobilePhone': user['mobilePhone'] if user['mobilePhone'] else None,
            'department': user['department'] if user['department'] else None,
            'companyName': user['companyName'] if user['companyName'] else None,
            'officeLocation': user['officeLocation'] if user['officeLocation'] else None,
            'proxyAddresses': [i.lower().replace('smtp:', '') for i in user['proxyAddresses'] if i.lower().startswith('smtp')],
            'accountEnabled': user['accountEnabled'],
            'onPremisesSyncEnabled': user['onPremisesSyncEnabled'],
            'onPremisesSamAccountName': user['onPremisesSamAccountName'],
            'lastPasswordChangeDateTime': user['lastPasswordChangeDateTime'],
            'assignedLicenses': [i['skuId'] for i in user['assignedLicenses']],
            'manager': {'id': user['manager']['id'], 'mail': user['manager']['mail']} if 'manager' in user else None,
        })

    if licensed:
        return [u for u in aad_users if u['assignedLicenses']]
    else:
        return aad_users


def ms_graph_users_signinactivity(licensed=False):
    """Query the MS Graph (Beta) API for a list of Azure AD account with sign-in activity.
    """
    token = ms_graph_client_token()
    if not token:  # The call to the MS API occassionally fails.
        return None

    headers = {
        "Authorization": "Bearer {}".format(token["access_token"]),
        'Content-Type': 'application/json',
        "ConsistencyLevel": "eventual",
    }
    url = "https://graph.microsoft.com/beta/users?$select=id,mail,userPrincipalName,signInActivity&$filter=endswith(mail,'@dbca.wa.gov.au')&$count=true"
    users = []
    resp = requests.get(url, headers=headers)
    j = resp.json()

    while '@odata.nextLink' in j:
        users = users + j['value']
        resp = requests.get(j['@odata.nextLink'], headers=headers)
        resp.raise_for_status()
        j = resp.json()

    users = users + j['value']  # Final page
    user_signins = {}

    for user in users:
        if 'signInActivity' in user and user['signInActivity']:
            user_signins[user['mail']] = user

    return user_signins


def ms_graph_inactive_users(days=45):
    """Query the MS Graph (Beta) API for a list of Azure AD accounts which haven't had a login event within a defined number of days.
    Returns a list of DepartmentUser objects.
    """
    from organisation.models import DepartmentUser  # Prevent circular imports.
    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    then = now - timedelta(days=days)
    token = ms_graph_client_token()
    if not token:  # The call to the MS API occassionally fails.
        return None

    headers = {"Authorization": "Bearer {}".format(token["access_token"]), "Content-Type": "application/json"}
    url = "https://graph.microsoft.com/beta/users?filter=signInActivity/lastSignInDateTime le {}".format(then.strftime('%Y-%m-%dT%H:%M:%SZ'))
    resp = requests.get(url, headers=headers)
    j = resp.json()
    accounts = j['value']  # At present the API doesn't return a paginated response.
    users = []

    for i in accounts:
        if i['accountEnabled'] and "#EXT#" not in i['userPrincipalName'] and i['userPrincipalName'].lower().endswith('dbca.wa.gov.au'):
            if DepartmentUser.objects.filter(active=True, email=i['userPrincipalName']).exists():
                user = DepartmentUser.objects.get(active=True, email=i['userPrincipalName'])
                if user.get_licence():
                    users.append(user)

    return users


def ms_graph_user(token, azure_guid):
    """Query the Microsoft Graph REST API details of a signle Azure AD user account in our tenancy.
    """
    headers = {
        "Authorization": "Bearer {}".format(token["access_token"]),
        "ConsistencyLevel": "eventual",
    }
    url = f"https://graph.microsoft.com/v1.0/user/{azure_guid}"
    resp = requests.get(url, headers=headers)
    return resp


def get_ad_users_json(container, azure_json_path):
    """Pass in the container name and path to a JSON dump of AD users, return parsed JSON.
    """
    connect_string = os.environ.get("AZURE_CONNECTION_STRING", None)
    if not connect_string:
        return None
    store = AzureBlobStorage(connect_string, container)
    return json.loads(store.get_content(azure_json_path))


def compare_values(a, b):
    """A utility function to compare two values for equality, with the exception that 'falsy' values
    (e.g. None and '') are equal. This is used to account for differences in how data is returned
    from the different AD environments and APIs.
    """
    if not a and not b:
        return True

    return a == b


def parse_windows_ts(s):
    """Parse the string repr of Windows timestamp output, a 64-bit value representing the number of
    100-nanoseconds elapsed since January 1, 1601 (UTC).
    """
    try:
        match = re.search('(?P<timestamp>[0-9]+)', s)
        return datetime.fromtimestamp(int(match.group()) / 1000)  # POSIX timestamp is in ms.
    except:
        return None


def department_user_ascender_sync(users):
    """For a passed-in queryset of Department Users and a file-like object, return a CSV containing
    data that should be synced to Ascender.
    """
    f = BytesIO()
    writer = csv.writer(f, quoting=csv.QUOTE_ALL, encoding='utf-8')
    writer.writerow(['EMPLOYEE_ID', 'EMAIL', 'ACTIVE', 'WORK_TELEPHONE', 'LICENCE_TYPE'])
    for user in users:
        writer.writerow([
            user.employee_id,
            user.email.lower(),
            user.active,
            user.telephone,
            user.get_licence(),
        ])
    return f
