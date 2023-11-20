from datetime import datetime, timedelta, timezone
from dateutil.parser import parse
from django.conf import settings
from io import BytesIO
import os
import pytz
import re
import requests
import unicodecsv as csv
from itassets.utils import ms_graph_client_token, upload_blob, get_blob_json

from .microsoft_products import MS_PRODUCTS

TZ = pytz.timezone(settings.TIME_ZONE)


def title_except(s, exceptions=None, acronyms=None):
    """Utility function to title-case words in a job title, except for all the exceptions and edge cases.
    """
    if not exceptions:
        exceptions = ('the', 'of', 'for', 'and', 'or')
    if not acronyms:
        acronyms = (
            'OIM', 'IT', 'PVS', 'SFM', 'OT', 'NP', 'FMDP', 'VRM', 'TEC', 'GIS', 'ODG', 'RIA', 'ICT',
            'RSD', 'CIS', 'PSB', 'FMB', 'CFO', 'BCS', 'CIO', 'EHP', 'FSB', 'FMP',
        )
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
    if not token:  # The call to the MS API occasionally fails.
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
    if not token:  # The call to the MS API occasionally fails.
        return None

    headers = {
        "Authorization": "Bearer {}".format(token["access_token"]),
    }
    azure_tenant_id = os.environ["AZURE_TENANT_ID"]
    url = f"https://graph.microsoft.com/v1.0/subscribedSkus/{azure_tenant_id}_{sku_id}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def ms_graph_users(licensed=False, token=None):
    """Query the Microsoft Graph REST API for Azure AD user accounts in our tenancy.
    Passing ``licensed=True`` will return only those users having >0 licenses assigned.
    Note that accounts are filtered to return only those with email *@dbca.wa.gov.au.
    Returns a list of Azure AD user objects (dicts).
    """
    if not token:
        token = ms_graph_client_token()
    if not token:  # The call to the MS API occasionally fails.
        return None

    headers = {
        "Authorization": "Bearer {}".format(token["access_token"]),
        "ConsistencyLevel": "eventual",
    }
    url = "https://graph.microsoft.com/v1.0/users?$select=id,mail,userPrincipalName,displayName,givenName,surname,employeeId,employeeType,jobTitle,businessPhones,mobilePhone,department,companyName,officeLocation,proxyAddresses,accountEnabled,onPremisesSyncEnabled,onPremisesSamAccountName,lastPasswordChangeDateTime,assignedLicenses&$filter=endswith(mail,'@dbca.wa.gov.au')&$count=true"
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
        })

    if licensed:
        return [u for u in aad_users if u['assignedLicenses']]
    else:
        return aad_users


def ms_graph_users_signinactivity(licensed=False, token=None):
    """Query the MS Graph API for a list of Azure AD account with sign-in activity.
    Passing ``licensed=True`` will return only those users having >0 licenses assigned.
    Note that accounts are filtered to return only those with email *@dbca.wa.gov.au.
    Returns a list of Azure AD user objects (dicts).
    """
    if not token:
        token = ms_graph_client_token()
    if not token:  # The call to the MS API occasionally fails and returns None.
        return None

    headers = {
        "Authorization": "Bearer {}".format(token["access_token"]),
        'Content-Type': 'application/json',
        "ConsistencyLevel": "eventual",
    }
    url = "https://graph.microsoft.com/v1.0/users?$select=id,mail,userPrincipalName,accountEnabled,assignedLicenses,signInActivity&$filter=endswith(mail,'@dbca.wa.gov.au')&$count=true"
    users = []
    resp = requests.get(url, headers=headers)
    j = resp.json()

    while '@odata.nextLink' in j:
        users = users + j['value']
        resp = requests.get(j['@odata.nextLink'], headers=headers)
        resp.raise_for_status()
        j = resp.json()

    users = users + j['value']  # Final page
    user_signins = []

    for user in users:
        if licensed:
            if 'signInActivity' in user and user['signInActivity'] and user['assignedLicenses']:
                user_signins.append(user)
        else:
            if 'signInActivity' in user and user['signInActivity']:
                user_signins.append(user)

    return user_signins


def ms_graph_dormant_accounts(days=90, licensed=False, token=None):
    """Query the MS Graph API for a list of Azure AD accounts which haven't had a login event
    within the defined number of ``days``.
    Passing ``licensed=True`` will return only those users having >0 licenses assigned.
    Note that accounts are filtered to return only those with email *@dbca.wa.gov.au, and that
    we classify 'dormant' accounts as though having no logins for ``days``.

    Returns a list of Azure AD account objects (dicts).
    """
    if not token:
        token = ms_graph_client_token()
    if not token:  # The call to the MS API occasionally fails and returns None.
        return None

    user_signins = ms_graph_users_signinactivity(licensed, token)
    if not user_signins:
        return None

    then = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    accounts = []
    for user in user_signins:
        accounts.append({
            'mail': user['mail'],
            'userPrincipalName': user['userPrincipalName'],
            'id': user['id'],
            'accountEnabled': user['accountEnabled'],
            'assignedLicenses': user['assignedLicenses'],
            'lastSignInDateTime': parse(user['signInActivity']['lastSignInDateTime']).astimezone(TZ) if user['signInActivity']['lastSignInDateTime'] else None,
        })

    # Excludes accounts with no 'last signed in' value.
    dormant_accounts = [i for i in accounts if i['lastSignInDateTime']]
    # Determine the list of AD accounts not having been signed into for the last number of `days`.
    dormant_accounts = [i for i in dormant_accounts if i['lastSignInDateTime'] <= then]

    if licensed:  # Filter the list to accounts having an E5/F3 license assigned.
        inactive_licensed = []
        for i in dormant_accounts:
            for license in i['assignedLicenses']:
                if license['skuId'] in [MS_PRODUCTS['MICROSOFT 365 E5'], MS_PRODUCTS['MICROSOFT 365 F3']]:
                    inactive_licensed.append(i)
        return inactive_licensed
    else:
        return dormant_accounts


def ms_graph_user(azure_guid, token=None):
    """Query the Microsoft Graph REST API details of a signle Azure AD user account in our tenancy.
    """
    if not token:
        token = ms_graph_client_token()
    if not token:  # The call to the MS API occasionally fails and returns None.
        return None
    headers = {
        "Authorization": "Bearer {}".format(token["access_token"]),
        "ConsistencyLevel": "eventual",
    }
    url = f"https://graph.microsoft.com/v1.0/user/{azure_guid}"
    resp = requests.get(url, headers=headers)
    return resp


def ms_graph_sites(team_sites=True, token=None):
    """Query the Microsoft Graph REST API for details about SharePoint Sites.
    Reference: https://learn.microsoft.com/en-us/graph/api/site-list
    """
    if not token:
        token = ms_graph_client_token()
    if not token:  # The call to the MS API occasionally fails and returns None.
        return None
    headers = {
        "Authorization": "Bearer {}".format(token["access_token"]),
        "ConsistencyLevel": "eventual",
    }
    url = "https://graph.microsoft.com/v1.0/sites"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    j = resp.json()

    sites = []
    while '@odata.nextLink' in j:
        sites = sites + j['value']
        resp = requests.get(j['@odata.nextLink'], headers=headers)
        resp.raise_for_status()
        j = resp.json()

    sites = sites + j['value']  # Final page.
    if team_sites:
        sites = [site for site in sites if 'teams' in site['webUrl']]

    return sites


def ms_graph_site_storage_usage(period_value="D7", token=None):
    """Query the MS Graph API to get the storage allocated and consumed by SharePoint sites.
    `period_value` is one of D7 (default), D30, D90 or D180. Returns the endpoint response content,
    which is a CSV report of all sites.

    Reference: https://learn.microsoft.com/en-us/graph/api/reportroot-getsharepointsiteusagestorage
    """
    if not token:
        token = ms_graph_client_token()
    if not token:  # The call to the MS API occasionally fails and returns None.
        return None
    headers = {
        "Authorization": "Bearer {}".format(token["access_token"]),
        "ConsistencyLevel": "eventual",
    }
    url = f"https://graph.microsoft.com/v1.0/reports/getSharePointSiteUsageDetail(period='{period_value}')"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()

    return resp.content


def ms_graph_site_storage_summary(ds=None):
    """Parses the current SharePoint site usage report, and returns a subset of storage usage data.
    """
    storage_usage = ms_graph_site_storage_usage()
    storage_csv = storage_usage.splitlines()
    headers = storage_csv[0].split(b",")
    headers = [h.decode() for h in headers]
    if not ds:  # Default to today's date.
        ds = datetime.today().strftime("%Y-%m-%d")

    f = BytesIO()
    writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
    writer.writerow([headers[0], headers[2], headers[5], headers[6], headers[10]])
    for row in storage_csv[1:]:
        row = row.split(b",")
        row = [i.decode() for i in row]
        if int(row[10]) >= 1024 * 1024 * 1024:  # Only return rows >= 1 GB.
            # We're only interested in some of the report output.
            writer.writerow([row[0], row[2].replace("https://dpaw.sharepoint.com/", ""), row[5], int(row[6]), int(row[10])])

    f.seek(0)
    blob_name = f"storage/site_storage_usage_{ds}.csv"
    upload_blob(in_file=f, container="analytics", blob=blob_name)


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
    """For a passed-in queryset of Department Users and a file-like object, returns a file-like
    object of CSV data that should be synced to Ascender.
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
    f.seek(0)
    return f


def nginx_hosts_upload(container="analytics", source_blob="nginx_host_proxy_targets.json", dest_blob="nginx_hosts.csv"):
    print("Downloading source data")
    hosts = get_blob_json(container, source_blob)
    f = BytesIO()
    writer = csv.writer(f, quoting=csv.QUOTE_ALL, encoding="utf-8")
    writer.writerow(["HOST", "SSO", "HTTPS RESPONSE"])

    for rule in hosts:
        host = rule["host"]
        if "sso_locations" in rule and rule["sso_locations"]:
            sso_locations = [i for i in rule["sso_locations"] if i]
        else:
            sso_locations = []
        if "/" in sso_locations or "^~ /" in sso_locations:
            sso = True
        else:
            sso = False

        # We can only check non-SSO sites.
        status_code = "Unknown"
        if not sso:
            print(f"Querying https://{host}")
            try:
                resp = requests.get(f"https://{host}", timeout=(3.05, 10))
                status_code = resp.status_code
            except requests.exceptions.SSLError:
                print("SSL error")
                status_code = "SSL Error"
            except requests.exceptions.Timeout:
                print("Timeout")
                status_code = "Timeout"
            except requests.exceptions.TooManyRedirects:
                print("Redirect loop")
                status_code = "Redirect loop"
            except:
                print("Error")
                status_code = "Error"
        else:
            print(f"Skipped {host} (SSO)")
        writer.writerow([host, sso, status_code])

    f.seek(0)
    print("Uploaded data to Azure")
    upload_blob(in_file=f, container="analytics", blob=dest_blob)
