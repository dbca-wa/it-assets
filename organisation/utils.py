import os
import re
from datetime import datetime, timedelta
from io import BytesIO
from typing import AnyStr, Dict, Iterable, List, Optional

import requests
import unicodecsv as csv
from dateutil.parser import parse
from django.conf import settings
from django.utils import timezone

from itassets.utils import ms_graph_client_token, upload_blob

from .microsoft_products import MS_PRODUCTS

FRESHSERVICE_AUTH = (settings.FRESHSERVICE_API_KEY, "X")


def title_except(s: str, exceptions: Optional[Iterable[str]] = None, acronyms: Optional[Iterable[str]] = None) -> AnyStr:
    """Utility function to title-case words in a job title, except for all the exceptions and edge cases."""
    if not exceptions:
        exceptions = ("the", "of", "for", "and", "or")
    if not acronyms:
        acronyms = (
            "OIM",
            "IT",
            "PVS",
            "SFM",
            "OT",
            "NP",
            "FMDP",
            "VRM",
            "TEC",
            "GIS",
            "ODG",
            "RIA",
            "ICT",
            "RSD",
            "CIS",
            "PSB",
            "FMB",
            "CFO",
            "BCS",
            "CIO",
            "EHP",
            "FSB",
            "FMP",
            "DBCA",
            "ZPA",
            "FOI",
            "ARP",
            "WA",
            "HR",
        )
    words = s.split()

    if words[0].startswith("A/"):
        words_title = ["A/" + words[0].replace("A/", "").capitalize()]
    elif words[0] in acronyms:
        words_title = [words[0]]
    else:
        words_title = [words[0].capitalize()]

    for word in words[1:]:
        word = word.lower()

        if word.startswith("("):
            pre = "("
            word = word.replace("(", "")
        else:
            pre = ""

        if word.endswith(")"):
            post = ")"
            word = word.replace(")", "")
        else:
            post = ""

        if word.replace(",", "").upper() in acronyms:
            word = word.upper()
        elif word in exceptions:
            pass
        else:
            word = word.capitalize()

        words_title.append(pre + word + post)

    return " ".join(words_title)


def ms_graph_subscribed_skus(token: Optional[dict] = None) -> List[Dict] | None:
    """Query the Microsoft Graph REST API for a list of commercial licence subscriptions.
    To map licence names against skuId, reference:
    https://docs.microsoft.com/en-us/azure/active-directory/enterprise-users/licensing-service-plan-reference
    """
    if not token:
        token = ms_graph_client_token()
    if not token:  # The call to the MS API occasionally fails.
        return None

    headers = {"Authorization": f"{token['token_type']} {token['access_token']}"}
    url = "https://graph.microsoft.com/v1.0/subscribedSkus"
    skus = []
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    j = resp.json()

    while "@odata.nextLink" in j:
        skus = skus + j["value"]
        resp = requests.get(j["@odata.nextLink"], headers=headers)
        resp.raise_for_status()
        j = resp.json()

    skus = skus + j["value"]  # Final page.
    return skus


def ms_graph_subscribed_sku(sku_id: str, token: Optional[dict] = None) -> Dict | None:
    if not token:
        token = ms_graph_client_token()
    if not token:  # The call to the MS API occasionally fails.
        return None

    headers = {"Authorization": f"Bearer {token['access_token']}"}
    azure_tenant_id = os.environ["AZURE_TENANT_ID"]
    url = f"https://graph.microsoft.com/v1.0/subscribedSkus/{azure_tenant_id}_{sku_id}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def ms_graph_users(licensed: bool = False, token: Optional[dict] = None):
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
        "Authorization": f"Bearer {token['access_token']}",
        "ConsistencyLevel": "eventual",
    }
    url = "https://graph.microsoft.com/v1.0/users?$select=id,mail,userPrincipalName,displayName,givenName,surname,employeeId,employeeType,jobTitle,businessPhones,mobilePhone,department,companyName,officeLocation,proxyAddresses,accountEnabled,onPremisesSyncEnabled,onPremisesSamAccountName,lastPasswordChangeDateTime,signInActivity,assignedLicenses,createdDateTime&$expand=manager($select=id,mail)"
    users = []
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    j = resp.json()

    while "@odata.nextLink" in j:
        users = users + j["value"]
        resp = requests.get(j["@odata.nextLink"], headers=headers)
        resp.raise_for_status()
        j = resp.json()

    users = users + j["value"]  # Final page
    entra_users = []

    for user in users:
        if not user["mail"] or not user["mail"].lower().endswith("@dbca.wa.gov.au"):
            continue
        user_data = {
            "objectId": user["id"],
            "mail": user["mail"].lower(),
            "userPrincipalName": user["userPrincipalName"],
            "displayName": user["displayName"] if user["displayName"] else None,
            "givenName": user["givenName"] if user["givenName"] else None,
            "surname": user["surname"] if user["surname"] else None,
            "employeeId": user["employeeId"] if user["employeeId"] else None,
            "employeeType": user["employeeType"] if user["employeeType"] else None,
            "jobTitle": user["jobTitle"] if user["jobTitle"] else None,
            "telephoneNumber": user["businessPhones"][0] if user["businessPhones"] else None,
            "mobilePhone": user["mobilePhone"] if user["mobilePhone"] else None,
            "department": user["department"] if user["department"] else None,
            "companyName": user["companyName"] if user["companyName"] else None,
            "officeLocation": user["officeLocation"] if user["officeLocation"] else None,
            "proxyAddresses": [i.lower().replace("smtp:", "") for i in user["proxyAddresses"] if i.lower().startswith("smtp")],
            "accountEnabled": user["accountEnabled"],
            "onPremisesSyncEnabled": user["onPremisesSyncEnabled"],
            "onPremisesSamAccountName": user["onPremisesSamAccountName"],
            "lastPasswordChangeDateTime": user["lastPasswordChangeDateTime"],
            "signInActivity": None,
            "createdDateTime": user["createdDateTime"],
            "assignedLicenses": [i["skuId"] for i in user["assignedLicenses"]],
            "manager": {"id": user["manager"]["id"], "mail": user["manager"]["mail"]} if "manager" in user else None,
        }
        if "signInActivity" in user:
            user_data["signInActivity"] = user["signInActivity"]

        entra_users.append(user_data)

    if licensed:
        return [u for u in entra_users if u["assignedLicenses"]]
    else:
        return entra_users


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
        "Authorization": f"Bearer {token['access_token']}",
        "Content-Type": "application/json",
        "ConsistencyLevel": "eventual",
    }
    url = "https://graph.microsoft.com/v1.0/users?$select=id,mail,userPrincipalName,accountEnabled,assignedLicenses,signInActivity&$filter=endswith(mail,'@dbca.wa.gov.au')&$count=true"
    users = []
    resp = requests.get(url, headers=headers)
    j = resp.json()

    while "@odata.nextLink" in j:
        users = users + j["value"]
        resp = requests.get(j["@odata.nextLink"], headers=headers)
        resp.raise_for_status()
        j = resp.json()

    users = users + j["value"]  # Final page
    user_signins = []

    for user in users:
        if licensed:
            if "signInActivity" in user and user["signInActivity"] and user["assignedLicenses"]:
                user_signins.append(user)
        else:
            if "signInActivity" in user and user["signInActivity"]:
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

    then = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    accounts = []
    for user in user_signins:
        accounts.append(
            {
                "mail": user["mail"],
                "userPrincipalName": user["userPrincipalName"],
                "id": user["id"],
                "accountEnabled": user["accountEnabled"],
                "assignedLicenses": user["assignedLicenses"],
                "lastSignInDateTime": parse(user["signInActivity"]["lastSignInDateTime"]).astimezone(settings.TZ)
                if user["signInActivity"]["lastSignInDateTime"]
                else None,
            }
        )

    # Excludes accounts with no 'last signed in' value.
    dormant_accounts = [i for i in accounts if i["lastSignInDateTime"]]
    # Determine the list of AD accounts not having been signed into for the last number of `days`.
    dormant_accounts = [i for i in dormant_accounts if i["lastSignInDateTime"] <= then]

    if licensed:  # Filter the list to accounts having an E5/F3 license assigned.
        inactive_licensed = []
        for i in dormant_accounts:
            for license in i["assignedLicenses"]:
                if license["skuId"] in [MS_PRODUCTS["MICROSOFT 365 E5"], MS_PRODUCTS["MICROSOFT 365 F3"]]:
                    inactive_licensed.append(i)
        return inactive_licensed
    else:
        return dormant_accounts


def ms_graph_user(azure_guid, token=None):
    """Query the Microsoft Graph REST API details of a signle Azure AD user account in our tenancy."""
    if not token:
        token = ms_graph_client_token()
    if not token:  # The call to the MS API occasionally fails and returns None.
        return None
    headers = {
        "Authorization": f"Bearer {token['access_token']}",
        "ConsistencyLevel": "eventual",
    }
    url = f"https://graph.microsoft.com/v1.0/users/{azure_guid}"
    resp = requests.get(url, headers=headers)
    return resp


def ms_graph_validate_password(password, token=None):
    """Query the Microsoft Graph REST API (beta) if a given password string validates complexity requirements."""
    if not token:
        token = ms_graph_client_token()
    if not token:  # The call to the MS API occasionally fails and returns None.
        return None
    headers = {
        "Authorization": f"Bearer {token['access_token']}",
    }
    url = "https://graph.microsoft.com/beta/users/validatePassword"
    resp = requests.post(url, headers=headers, json={"password": password})
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
        "Authorization": f"Bearer {token['access_token']}",
        "ConsistencyLevel": "eventual",
    }
    url = "https://graph.microsoft.com/v1.0/sites"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    j = resp.json()

    sites = []
    while "@odata.nextLink" in j:
        sites = sites + j["value"]
        resp = requests.get(j["@odata.nextLink"], headers=headers)
        resp.raise_for_status()
        j = resp.json()

    sites = sites + j["value"]  # Final page.
    if team_sites:
        sites = [site for site in sites if "teams" in site["webUrl"]]

    return sites


def ms_graph_site_detail(site_id, token=None):
    """Query the MS Graph API for details of a single Sharepoint site.
    Ref: https://learn.microsoft.com/en-us/graph/api/site-get
    """
    if not token:
        token = ms_graph_client_token()
    if not token:  # The call to the MS API occasionally fails and returns None.
        return None
    headers = {
        "Authorization": f"Bearer {token['access_token']}",
    }
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()

    return resp.json()


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
        "Authorization": f"Bearer {token['access_token']}",
        "ConsistencyLevel": "eventual",
    }
    url = f"https://graph.microsoft.com/v1.0/reports/getSharePointSiteUsageDetail(period='{period_value}')"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()

    return resp.content


def ms_graph_site_storage_summary(ds=None, token=None):
    """Parses the current SharePoint site usage report, and returns a subset of storage usage data."""
    if not token:
        token = ms_graph_client_token()
    if not token:  # The call to the MS API occasionally fails and returns None.
        return None

    storage_usage = ms_graph_site_storage_usage(token=token)
    storage_csv = storage_usage.splitlines()
    header_row = storage_csv[0].split(b",")
    header_row = [h.decode("utf-8-sig") for h in header_row]  # Decode without byte order mark.
    if not ds:  # Default to today's date.
        ds = datetime.today().strftime("%Y-%m-%d")

    f = BytesIO()
    writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
    writer.writerow([header_row[0], header_row[2], header_row[5], header_row[6], header_row[10]])
    for row in storage_csv[1:]:
        row = row.decode()
        row = row.split(",")
        # We're only interested in some of the report output.
        if int(row[10]) >= 1024 * 1024 * 1024:  # Only return rows >= 1 GB.
            # TEMP FIX: Microsoft reported an issue where usage reports are incomplete for Sharepoint.
            # Query each site ID to get the site URL.
            # Ref: https://stackoverflow.com/a/77550299/14508
            site_id = row[1]
            try:
                site_json = ms_graph_site_detail(site_id, token)
                site_url = site_json["webUrl"].replace("https://dpaw.sharepoint.com", "")
            except:
                site_url = ""
            writer.writerow([row[0], site_url, row[5], int(row[6]), int(row[10])])

    f.seek(0)
    blob_name = f"storage/site_storage_usage_{ds}.csv"
    upload_blob(in_file=f, container="analytics", blob=blob_name)


def compare_values(a, b) -> bool:
    """A utility function to compare two values for equality, with the exception that 'falsy' values
    (e.g. None and '') are equal. This is used to account for differences in how data is returned
    from the different AD environments and APIs.
    """
    if not a and not b:
        return True

    return a == b


def parse_windows_ts(ts: str) -> datetime | None:
    """Parse the string repr of Windows timestamp output, a 64-bit value representing the number of
    100-nanoseconds elapsed since January 1, 1601 (UTC).
    """
    try:
        match = re.search("(?P<timestamp>[0-9]+)", ts)
        return datetime.fromtimestamp(int(match.group()) / 1000)  # POSIX timestamp is in ms.
    except:
        return None


def parse_ad_pwd_last_set(pwd_last_set: int) -> datetime:
    """Parse onprem AD Pwd-Last-Set integer as a TZ-aware datetime.
    Onprem AD accounts store the Pwd-Last-Set attribute as a large integer representing the number of
    100 nanosecond intervals since January 1, 1601 (UTC).
    Reference: https://learn.microsoft.com/en-us/windows/win32/adschema/a-pwdlastset
    """
    return (datetime(1601, 1, 1) + timedelta(microseconds=pwd_last_set / 10)).astimezone(settings.TZ)


def get_freshservice_objects(obj_type) -> List[Dict]:
    """Query the Freshservice v2 API for objects of a defined type."""
    url = f"{settings.FRESHSERVICE_ENDPOINT}/{obj_type}"
    params = {
        "page": 1,
        "per_page": 100,
    }
    objects = []
    further_results = True

    while further_results:
        print(f"Downloading page {params['page']}")
        resp = requests.get(url, auth=FRESHSERVICE_AUTH, params=params)
        resp.raise_for_status()
        if "link" not in resp.headers:  # No further paginated results.
            further_results = False
        else:
            print(resp.headers["link"])

        objects.extend(resp.json()[obj_type])
        params["page"] += 1

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

    url = f"{settings.FRESHSERVICE_ENDPOINT}/{obj_type}"
    resp = requests.post(url, auth=FRESHSERVICE_AUTH, json=data)

    return resp


def update_freshservice_object(obj_type, id, data):
    """Use the Freshservice v2 API to update an object.
    Accepts an object type name (string), object ID and a dict of key values.
    """

    url = f"{settings.FRESHSERVICE_ENDPOINT}/{obj_type}/{id}"
    resp = requests.put(url, auth=FRESHSERVICE_AUTH, json=data)

    return resp
