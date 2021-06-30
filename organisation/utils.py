from data_storage import AzureBlobStorage
from datetime import datetime
from django.conf import settings
import json
import os
import pytz
import re
import requests
from itassets.utils import ms_graph_client_token

TZ = pytz.timezone(settings.TIME_ZONE)


def ascender_onprem_ad_data_diff(container='azuread', json_path='adusers.json'):
    """A utility function to compare on-premise AD user account data with Ascender HR data.
    """
    from .models import DepartmentUser
    discrepancies = []

    # Iterate through DepartmentUsers and check for mismatches between Ascender and onprem AD data.
    for user in DepartmentUser.objects.filter(employee_id__isnull=False, ascender_data__isnull=False, ad_guid__isnull=False, ad_data__isnull=False):

        # First name - check against preferred name, then first name.
        name_mismatch = False
        if user.ascender_data['preferred_name']:
            if user.ad_data['GivenName'].upper() != user.ascender_data['preferred_name'].upper() and user.ad_data['GivenName'].upper() != user.ascender_data['first_name'].upper():
                name_mismatch = True
        else:
            if user.ad_data['GivenName'].upper() != user.ascender_data['first_name'].upper():
                name_mismatch = True
        if name_mismatch:
            discrepancies.append({
                'ascender_id': user.employee_id,
                'target': 'On-premise AD',
                'target_pk': user.ad_guid,
                'field': 'GivenName',
                'old_value': user.ad_data['GivenName'],
                'new_value': user.ascender_data['preferred_name'] if user.ascender_data['preferred_name'] else user.ascender_data['first_name'],
                'action': 'Update onprem AD user {} GivenName to {}'.format(user.ad_guid, user.ascender_data['preferred_name'] if user.ascender_data['preferred_name'] else user.ascender_data['first_name']),
            })

        # Surname.
        if user.ad_data['Surname'].upper() != user.ascender_data['surname'].upper():
            discrepancies.append({
                'ascender_id': user.employee_id,
                'target': 'On-premise AD',
                'target_pk': user.ad_guid,
                'field': 'Surname',
                'old_value': user.ad_data['Surname'],
                'new_value': user.ascender_data['surname'],
                'action': 'Update onprem AD user {} Surname to {}'.format(user.ad_guid, user.ascender_data['surname']),
            })

        # Phone number (disregard differences in spaces and brackets).
        if user.ad_data['telephoneNumber']:
            ad_tel = user.ad_data['telephoneNumber'].replace('(', '').replace(')', '').replace(' ', '')
        else:
            ad_tel = ''
        if user.ascender_data['work_phone_no']:
            asc_tel = user.ascender_data['work_phone_no'].replace('(', '').replace(')', '').replace(' ', '')
        else:
            asc_tel = ''
        if ad_tel != asc_tel:
            discrepancies.append({
                'ascender_id': user.employee_id,
                'target': 'On-premise AD',
                'target_pk': user.ad_guid,
                'field': 'OfficePhone',
                'old_value': user.ad_data['telephoneNumber'],
                'new_value': user.ascender_data['work_phone_no'],
                'action': 'Update onprem AD user {} OfficePhone to {}'.format(user.ad_guid, user.ascender_data['work_phone_no']),
            })

        # Mobile number (disregard differences in spaces).
        if user.ad_data['Mobile']:
            ad_mob = user.ad_data['Mobile'].replace(' ', '')
        else:
            ad_mob = ''
        if user.ascender_data['work_mobile_phone_no']:
            asc_mob = user.ascender_data['work_mobile_phone_no'].replace(' ', '')
        else:
            asc_mob = ''
        if ad_mob != asc_mob:
            discrepancies.append({
                'ascender_id': user.employee_id,
                'target': 'On-premise AD',
                'target_pk': user.ad_guid,
                'field': 'MobilePhone',
                'old_value': user.ad_data['Mobile'],
                'new_value': user.ascender_data['work_mobile_phone_no'],
                'action': 'Update onprem AD user {} MobilePhone to {}'.format(user.ad_guid, user.ascender_data['work_mobile_phone_no']),
            })

        # Title
        if user.ad_data['Title']:
            ad_title = user.ad_data['Title'].upper()
        else:
            ad_title = ''
        if user.ascender_data['occup_pos_title']:
            asc_title = user.ascender_data['occup_pos_title'].upper()
        else:
            asc_title = ''
        if ad_title != asc_title:
            discrepancies.append({
                'ascender_id': user.employee_id,
                'target': 'On-premise AD',
                'target_pk': user.ad_guid,
                'field': 'Title',
                'old_value': user.ad_data['Title'],
                'new_value': user.ascender_data['occup_pos_title'],
                'action': 'Update onprem AD user {} Title to {}'.format(user.ad_guid, user.ascender_data['occup_pos_title']),
            })

        # Cost centre
        # We have to handle these a bit differently to the above.
        new_cc = None
        if user.ad_data['Company']:
            ad_cc = user.ad_data['Company'].replace('RIA-', '').replace('ZPA-', '').replace('DBCA-', '')
        else:
            ad_cc = ''

        if user.ascender_data['paypoint'].startswith('R') and user.ascender_data['paypoint'].replace('R', '') != ad_cc:
            new_cc = user.ascender_data['paypoint'].replace('R', 'RIA-')
        elif user.ascender_data['paypoint'].startswith('Z') and user.ascender_data['paypoint'].replace('Z', '') != ad_cc:
            new_cc = user.ascender_data['paypoint'].replace('Z', 'ZPA-')
        elif user.ascender_data['paypoint'][0] in '1234567890' and user.ascender_data['paypoint'] != ad_cc:
            new_cc = 'DBCA-{}'.format(user.ascender_data['paypoint'])
        # TODO: differences for BGPA cost centres.
        if new_cc:
            discrepancies.append({
                'ascender_id': user.employee_id,
                'target': 'On-premise AD',
                'target_pk': user.ad_guid,
                'field': 'Company',
                'old_value': user.ad_data['Company'],
                'new_value': new_cc,
                'action': 'Update onprem AD user {} Company to {}'.format(user.ad_guid, new_cc),
            })

    return discrepancies


def ms_graph_users(licensed=False):
    """Query the Microsoft Graph REST API for on-premise user accounts in our tenancy.
    Passing ``licensed=True`` will return only those users having >0 licenses assigned.
    """
    token = ms_graph_client_token()
    headers = {
        "Authorization": "Bearer {}".format(token["access_token"]),
        "ConsistencyLevel": "eventual",
    }
    url = "https://graph.microsoft.com/v1.0/users?$select=id,mail,displayName,givenName,surname,employeeId,employeeType,jobTitle,businessPhones,mobilePhone,companyName,officeLocation,proxyAddresses,accountEnabled,onPremisesSyncEnabled,assignedLicenses&$filter=endswith(mail,'@dbca.wa.gov.au')&$orderby=userPrincipalName&$count=true"
    users = []
    resp = requests.get(url, headers=headers)
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
            'displayName': user['displayName'] if user['displayName'] else '',
            'givenName': user['givenName'] if user['givenName'] else '',
            'surname': user['surname'] if user['surname'] else '',
            'employeeId': user['employeeId'] if user['employeeId'] else '',
            'employeeType': user['employeeType'] if user['employeeType'] else '',
            'jobTitle': user['jobTitle'] if user['jobTitle'] else '',
            'telephoneNumber': user['businessPhones'][0] if user['businessPhones'] else '',
            'mobilePhone': user['mobilePhone'] if user['mobilePhone'] else '',
            'companyName': user['companyName'] if user['companyName'] else '',
            'officeLocation': user['officeLocation'] if user['officeLocation'] else '',
            'proxyAddresses': [i.lower().replace('smtp:', '') for i in user['proxyAddresses'] if i.lower().startswith('smtp')],
            'accountEnabled': user['accountEnabled'],
            'onPremisesSyncEnabled': user['onPremisesSyncEnabled'],
            'assignedLicenses': [i['skuId'] for i in user['assignedLicenses']],
        })

    if licensed:
        return [u for u in aad_users if u['assignedLicenses']]
    else:
        return aad_users


def get_ad_users_json(container, azure_json_path):
    """Pass in the container name and path to a JSON dump of AD users, return parsed JSON.
    """
    connect_string = os.environ.get("AZURE_CONNECTION_STRING", None)
    if not connect_string:
        return None
    store = AzureBlobStorage(connect_string, container)
    return json.loads(store.get_content(azure_json_path))


def onprem_ad_data_import(container='azuread', json_path='adusers.json', verbose=False):
    """Utility function to download onprem AD data from blob storage, then copy it to matching DepartmentUser objects.
    """
    from organisation.models import DepartmentUser
    ad_users = get_ad_users_json(container=container, azure_json_path=json_path)
    ad_users = {i['ObjectGUID']: i for i in ad_users}

    for k, v in ad_users.items():
        if DepartmentUser.objects.filter(ad_guid=k).exists():
            du = DepartmentUser.objects.get(ad_guid=k)
            du.ad_data = v
            du.ad_data_updated = TZ.localize(datetime.now())
            du.save()
        else:
            if verbose:
                print("Could not match onprem AD GUID {} to a department user".format(k))


def azure_ad_data_import(verbose=False):
    """Utility function to download Azure AD data from MS Graph API, then copy it to matching DepartmentUser objects.
    """
    from organisation.models import DepartmentUser
    azure_ad_users = ms_graph_users(licensed=True)
    azure_ad_users = {u['objectId']: u for u in azure_ad_users}

    for k, v in azure_ad_users.items():
        if DepartmentUser.objects.filter(azure_guid=k).exists():
            du = DepartmentUser.objects.get(azure_guid=k)
            du.azure_ad_data = v
            du.azure_ad_data_updated = TZ.localize(datetime.now())
            du.save()
        else:
            if verbose:
                print("Could not match Azure GUID {} to a department user".format(k))


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
