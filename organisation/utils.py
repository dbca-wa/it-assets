from data_storage import AzureBlobStorage
from datetime import datetime, date
from django.conf import settings
import json
import os
import pytz
import requests
from itassets.utils import ms_graph_client_token
from organisation.ascender import ascender_employee_fetch
from organisation.models import DepartmentUser

TZ = pytz.timezone(settings.TIME_ZONE)


def ascender_onprem_ad_diff(container='azuread', json_path='adusers.json'):
    """A utility function to compare Ascender user data with on-premise AD data.
    """
    print("Getting Ascender data")
    employee_iter = ascender_employee_fetch()
    ascender_users = {}
    for eid, jobs in employee_iter:
        # Exclude FPC employees and terminated employees.
        job = jobs[0]
        if job['clevel1_id'] != 'FPC' and not job['job_term_date']:
            ascender_users[eid] = job

    print("Downloading on-premise AD data")
    ad_users = get_azure_users_json(container=container, azure_json_path=json_path)
    ad_users = {u['ObjectGUID']: u for u in ad_users}
    discrepancies = []

    # Iterate through the Ascender data, checking for mismatches with on-prem AD data.
    for emp_id, user in ascender_users.items():
        ad_user = None

        # Find the matching AD user.
        for ad in ad_users.values():
            if ad['EmployeeID'] == emp_id:
                ad_user = ad
                break

        if ad_user:
            print("Checking {} against {}".format(emp_id, ad_user['EmailAddress']))

            # First name.
            if ad_user['GivenName'].upper() != user['first_name']:
                discrepancies.append({
                    'ascender_id': user['employee_id'],
                    'target': 'Onprem AD',
                    'target_pk': ad_user['ObjectGUID'],
                    'field': 'GivenName',
                    'old_value': ad_user['GivenName'],
                    'new_value': user['first_name'].capitalize(),
                    'action': 'Update onprem AD user {} GivenName to {}'.format(ad_user['ObjectGUID'], user['first_name'].capitalize()),
                })

            # Surname.
            if ad_user['Surname'].upper() != user['surname']:
                discrepancies.append({
                    'ascender_id': user['employee_id'],
                    'target': 'Onprem AD',
                    'target_pk': ad_user['ObjectGUID'],
                    'field': 'Surname',
                    'old_value': ad_user['Surname'],
                    'new_value': user['surname'].capitalize(),
                    'action': 'Update onprem AD user {} Surname to {}'.format(ad_user['ObjectGUID'], user['surname'].capitalize()),
                })

            # Phone number.
            if ad_user['telephoneNumber'] != user['work_phone_no']:
                discrepancies.append({
                    'ascender_id': user['employee_id'],
                    'target': 'Onprem AD',
                    'target_pk': ad_user['ObjectGUID'],
                    'field': 'telephoneNumber',
                    'old_value': ad_user['telephoneNumber'],
                    'new_value': user['work_phone_no'],
                    'action': 'Update onprem AD user {} telephoneNumber to {}'.format(ad_user['ObjectGUID'], user['work_phone_no']),
                })

            # Title
            if ad_user['Title'].upper() != user['occup_pos_title']:
                discrepancies.append({
                    'ascender_id': user['employee_id'],
                    'target': 'Onprem AD',
                    'target_pk': ad_user['ObjectGUID'],
                    'field': 'Title',
                    'old_value': ad_user['Title'],
                    'new_value': user['occup_pos_title'].title(),
                    'action': 'Update onprem AD user {} Title to {}'.format(ad_user['ObjectGUID'], user['occup_pos_title'].title()),
                })

            # Cost centre
            if user['paypoint'] and user['paypoint'] != ad_user['Company']:
                cc = False
                if user['paypoint'].startswith('R') and user['paypoint'].replace('R', '') != ad_user['Company'].replace('RIA-', ''):
                    cc = user['paypoint'].replace('R', 'RIA-')
                elif user['paypoint'].startswith('Z') and user['paypoint'].replace('Z', '') != ad_user['Company'].replace('ZPA-', ''):
                    cc = user['paypoint'].replace('Z', 'ZPA-')
                elif user['paypoint'][0] in '1234567890' and user['paypoint'] != ad_user['Company'].replace('DBCA-', ''):
                    cc = 'DBCA-{}'.format(user['paypoint'])
                # TODO: differences for BGPA cost centres.
                if cc:
                    discrepancies.append({
                        'ascender_id': user['employee_id'],
                        'target': 'Onprem AD',
                        'target_pk': ad_user['ObjectGUID'],
                        'field': 'Company',
                        'old_value': ad_user['Company'],
                        'new_value': cc,
                        'action': 'Update onprem AD user {} Company to {}'.format(ad_user['ObjectGUID'], cc),
                    })
        else:
            print("{} didn't match any on-premise AD user".format(emp_id))

    return discrepancies


def ascender_onprem_ad_data_diff():
    """A utility function to compare on-premise user account data with Ascender HR data.
    """
    print("Downloading Ascender data")
    employee_iter = ascender_employee_fetch()
    ascender_users = {}
    for eid, jobs in employee_iter:
        # Exclude FPC employees and employee having a job that is terminated.
        job = jobs[0]
        if job['clevel1_id'] != 'FPC':
            if not job['job_term_date'] or datetime.strptime(job['job_term_date'], '%Y-%m-%d').date() >= date.today():
                ascender_users[eid] = job

    print("Downloading on-prem AD data")
    ad_users = get_azure_users_json(container='azuread', azure_json_path='adusers.json')
    discrepancies = []

    # Iterate through the Ascender data, checking for mismatches with Azure AD data.
    for emp_id, user in ascender_users.items():
        ad_user = None

        # Find the matching Azure AD user.
        for u in ad_users:
            if 'EmployeeID' in u and u['EmployeeID'] == emp_id:
                ad_user = u
                break

        if ad_user:
            print("Checking {} against {}".format(emp_id, ad_user['EmailAddress']))

            # First name.
            if ad_user['GivenName'].upper() != user['first_name']:
                discrepancies.append({
                    'ascender_id': user['employee_id'],
                    'target': 'On-premise AD',
                    'target_pk': ad_user['ObjectGUID'],
                    'field': 'GivenName',
                    'old_value': ad_user['GivenName'],
                    'new_value': user['first_name'].capitalize(),
                    'action': 'Update onprem AD user {} GivenName to {}'.format(ad_user['ObjectGUID'], user['first_name'].capitalize()),
                })

            # Surname.
            if ad_user['Surname'].upper() != user['surname']:
                discrepancies.append({
                    'ascender_id': user['employee_id'],
                    'target': 'On-premise AD',
                    'target_pk': ad_user['ObjectGUID'],
                    'field': 'Surname',
                    'old_value': ad_user['Surname'],
                    'new_value': user['surname'].capitalize(),
                    'action': 'Update onprem AD user {} Surname to {}'.format(ad_user['ObjectGUID'], user['surname'].capitalize()),
                })

            # Phone number.
            if ad_user['telephoneNumber'] != user['work_phone_no']:
                discrepancies.append({
                    'ascender_id': user['employee_id'],
                    'target': 'On-premise AD',
                    'target_pk': ad_user['ObjectGUID'],
                    'field': 'telephoneNumber',
                    'old_value': ad_user['telephoneNumber'],
                    'new_value': user['work_phone_no'],
                    'action': 'Update onprem AD user {} telephoneNumber to {}'.format(ad_user['ObjectGUID'], user['work_phone_no']),
                })

            # Title
            if ad_user['Title'].upper() != user['occup_pos_title']:
                discrepancies.append({
                    'ascender_id': user['employee_id'],
                    'target': 'On-premise AD',
                    'target_pk': ad_user['ObjectGUID'],
                    'field': 'Title',
                    'old_value': ad_user['Title'],
                    'new_value': user['occup_pos_title'].title(),
                    'action': 'Update onprem AD user {} Title to {}'.format(ad_user['ObjectGUID'], user['occup_pos_title'].title()),
                })

            # Cost centre
            # We have to handle these a bit differently to the above.
            if user['paypoint'] and user['paypoint'] != ad_user['Company']:
                cc = False
                if user['paypoint'].startswith('R') and user['paypoint'].replace('R', '') != ad_user['Company'].replace('RIA-', ''):
                    cc = True
                    new_value = user['paypoint'].replace('R', 'RIA-')
                elif user['paypoint'].startswith('Z') and user['paypoint'].replace('Z', '') != ad_user['Company'].replace('ZPA-', ''):
                    cc = True
                    new_value = user['paypoint'].replace('Z', 'ZPA-')
                elif user['paypoint'][0] in '1234567890' and user['paypoint'] != ad_user['Company'].replace('DBCA-', ''):
                    cc = True
                    new_value = 'DBCA-{}'.format(user['paypoint'])
                # TODO: differences for BGPA cost centres.
                if cc:
                    discrepancies.append({
                        'ascender_id': user['employee_id'],
                        'target': 'On-premise AD',
                        'target_pk': ad_user['ObjectGUID'],
                        'field': 'Company',
                        'old_value': ad_user['Company'],
                        'new_value': new_value,
                        'action': 'Update onprem AD user {} Company to {}'.format(ad_user['ObjectGUID'], new_value),
                    })
        else:
            print("{} didn't match any onprem AD user".format(emp_id))

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


def get_azure_users_json(container, azure_json_path):
    """Pass in the container name and path to a JSON dump of Azure AD users, return parsed JSON.
    Deprecated in favour of the ms_graph_users function.
    """
    connect_string = os.environ.get("AZURE_CONNECTION_STRING", None)
    if not connect_string:
        return None
    store = AzureBlobStorage(connect_string, container)
    return json.loads(store.get_content(azure_json_path))


def find_user_in_list(user_list, email=None, objectid=None):
    """For a list of dicts (Azure/onprem AD users), find the first one matching email/objectid (or None).
    """
    if email:
        for user in user_list:
            if 'mail' in user and user['mail'] and user['mail'].lower() == email.lower():  # Azure AD
                return user
            elif 'EmailAddress' in user and user['EmailAddress'] and user['EmailAddress'].lower() == email.lower():  # Onprem AD
                return user
    if objectid:
        for user in user_list:
            if 'objectId' in user and user['objectId'] and user['objectId'] == objectid:  # Azure AD
                return user
            elif 'ObjectGUID' in user and user['ObjectGUID'] and user['ObjectGUID'] == objectid:  # Onprem AD
                return user
    return None


def update_deptuser_from_onprem_ad(ad_user, dept_user):
    """For given onprem AD user and DepartmentUser objects, update the DepartmentUser object fields
    with values from AD (the source of truth for these values).
    Currently, only ObjectGUID and SamAccountName should be synced from on-prem AD.
    """
    dept_user.ad_guid = ad_user['ObjectGUID']
    dept_user.username = ad_user['SamAccountName']
    dept_user.save()


def update_deptuser_from_azure(dept_user):
    """For a given DepartmentUser object, update the DepartmentUser object fields
    with values from the cached Azure AD data (the source of truth for these values).
    """
    if 'accountEnabled' in dept_user.azure_ad_data and dept_user.azure_ad_data['accountEnabled'] != dept_user.active:
        dept_user.active = dept_user.azure_ad_data['accountEnabled']
    if 'mail'in dept_user.azure_ad_data and dept_user.azure_ad_data['mail'] != dept_user.email:
        dept_user.email = dept_user.azure_ad_data['mail']
    if 'displayName' in dept_user.azure_ad_data and dept_user.azure_ad_data['displayName'] != dept_user.name:
        dept_user.name = dept_user.azure_ad_data['displayName']
    if 'givenName' in dept_user.azure_ad_data and dept_user.azure_ad_data['givenName'] != dept_user.given_name:
        dept_user.given_name = dept_user.azure_ad_data['givenName']
    if 'surname' in dept_user.azure_ad_data and dept_user.azure_ad_data['surname'] != dept_user.surname:
        dept_user.surname = dept_user.azure_ad_data['surname']
    if 'onPremisesSyncEnabled' in dept_user.azure_ad_data and dept_user.azure_ad_data['onPremisesSyncEnabled'] != dept_user.dir_sync_enabled:
        dept_user.dir_sync_enabled = dept_user.azure_ad_data['onPremisesSyncEnabled']

    if 'proxyAddresses' in dept_user.azure_ad_data:
        dept_user.proxy_addresses = [i.lower().replace('smtp:', '') for i in dept_user.azure_ad_data['proxyAddresses'] if i.lower().startswith('smtp')]

    dept_user.assigned_licences = []
    # MS licence SKU reference:
    # https://docs.microsoft.com/en-us/azure/active-directory/users-groups-roles/licensing-service-plan-reference
    ms_licence_skus = {
        'c5928f49-12ba-48f7-ada3-0d743a3601d5': 'VISIO Online Plan 2',  # VISIOCLIENT
        '1f2f344a-700d-42c9-9427-5cea1d5d7ba6': 'STREAM',
        'b05e124f-c7cc-45a0-a6aa-8cf78c946968': 'ENTERPRISE MOBILITY + SECURITY E5',  # EMSPREMIUM
        'c7df2760-2c81-4ef7-b578-5b5392b571df': 'OFFICE 365 E5',  # ENTERPRISEPREMIUM
        '87bbbc60-4754-4998-8c88-227dca264858': 'POWERAPPS_INDIVIDUAL_USER',
        '6470687e-a428-4b7a-bef2-8a291ad947c9': 'WINDOWS_STORE',
        '6fd2c87f-b296-42f0-b197-1e91e994b900': 'OFFICE 365 E3',  # ENTERPRISEPACK
        'f30db892-07e9-47e9-837c-80727f46fd3d': 'FLOW_FREE',
        '440eaaa8-b3e0-484b-a8be-62870b9ba70a': 'PHONESYSTEM_VIRTUALUSER',
        'bc946dac-7877-4271-b2f7-99d2db13cd2c': 'FORMS_PRO',
        'dcb1a3ae-b33f-4487-846a-a640262fadf4': 'POWERAPPS_VIRAL',
        '338148b6-1b11-4102-afb9-f92b6cdc0f8d': 'DYN365_ENTERPRISE_P1_IW',
        '6070a4c8-34c6-4937-8dfb-39bbc6397a60': 'MEETING_ROOM',
        'a403ebcc-fae0-4ca2-8c8c-7a907fd6c235': 'POWER_BI_STANDARD',
        '111046dd-295b-4d6d-9724-d52ac90bd1f2': 'Microsoft Defender Advanced Threat Protection',  # WIN_DEF_ATP
        '710779e8-3d4a-4c88-adb9-386c958d1fdf': 'TEAMS_EXPLORATORY',
        'efccb6f7-5641-4e0e-bd10-b4976e1bf68e': 'ENTERPRISE MOBILITY + SECURITY E3',  # EMS
        '90d8b3f8-712e-4f7b-aa1e-62e7ae6cbe96': 'SMB_APPS',
        'fcecd1f9-a91e-488d-a918-a96cdb6ce2b0': 'AX7_USER_TRIAL',
        '093e8d14-a334-43d9-93e3-30589a8b47d0': 'RMSBASIC',
        '53818b1b-4a27-454b-8896-0dba576410e6': 'PROJECT ONLINE PROFESSIONAL',  # PROJECTPROFESSIONAL
        '18181a46-0d4e-45cd-891e-60aabd171b4e': 'OFFICE 365 E1',  # STANDARDPACK
        '06ebc4ee-1bb5-47dd-8120-11324bc54e06': 'MICROSOFT 365 E5',
        '66b55226-6b4f-492c-910c-a3b7a3c9d993': 'MICROSOFT 365 F3',
        '05e9a617-0261-4cee-bb44-138d3ef5d965': 'MICROSOFT 365 E3',
    }
    if 'assigned_licences' in dept_user.azure_ad_data:
        for sku in dept_user.azure_ad_data['assignedLicenses']:
            if sku in ms_licence_skus:
                dept_user.assigned_licences.append(ms_licence_skus[sku])
            else:
                dept_user.assigned_licences.append(sku)

    dept_user.save()


def departmentuser_ad_sync(dept_user):
    """Utility function to perform all of the steps to sync up a single DepartmentUser and Active Directory.
    Function may be run as-is, or queued as an asynchronous task.
    """
    if dept_user.azure_ad_data:
        update_deptuser_from_azure(dept_user)
    dept_user.generate_ad_actions()
    dept_user.audit_ad_actions()


def onprem_ad_data_import(container='azuread', json_path='adusers.json', verbose=False):
    """Utility function to download onprem AD data from blob storage, then copy it to matching DepartmentUser objects.
    """
    ad_users = get_azure_users_json(container=container, azure_json_path=json_path)
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
