from data_storage import AzureBlobStorage
from datetime import datetime, timedelta
from dbca_utils.utils import env
from django.core.files.base import ContentFile
import json
import os
import re


def get_azure_users_json(container, azure_json_path):
    """Pass in the container name and path to a JSON dump of Azure AD users, return parsed JSON.
    """
    connect_string = env('AZURE_CONNECTION_STRING', '')
    if not connect_string:
        return None
    store = AzureBlobStorage(connect_string, container)
    return json.loads(store.get_content(azure_json_path))


def find_user_in_list(user_list, email=None, objectid=None):
    """For a list of dicts (Azure AD users), find the first one matching email/objectid (or None).
    """
    if email:
        for user in user_list:
            if user['Mail'] and user['Mail'].lower() == email.lower():
                return user
    if objectid:
        for user in user_list:
            if user['ObjectId'] and user['ObjectId'] == objectid:
                return user
    return None


def update_deptuser_from_azure(azure_user, dept_user):
    """For given Azure AD user and DepartmentUser objects, update the DepartmentUser object fields
    with values from Azure (the source of truth for these values).
    """
    dept_user.azure_guid = azure_user['ObjectId']
    # dept_user.active = azure_user['AccountEnabled']
    dept_user.dir_sync_enabled = azure_user['DirSyncEnabled']
    licence_pattern = 'SkuId:\s[a-z0-9-]+'
    dept_user.mail_nickname = azure_user['MailNickName']
    dept_user.proxy_addresses = [i.lower().replace('smtp:', '') for i in azure_user['ProxyAddresses'] if i.lower().startswith('smtp')]

    skus = [re.search(licence_pattern, i)[0].replace('SkuId: ', '') for i in azure_user['AssignedLicenses'] if re.search(licence_pattern, i)]
    dept_user.assigned_licences = []
    ms_licence_skus = {
        'c5928f49-12ba-48f7-ada3-0d743a3601d5': 'VISIOCLIENT',
        '1f2f344a-700d-42c9-9427-5cea1d5d7ba6': 'STREAM',
        'b05e124f-c7cc-45a0-a6aa-8cf78c946968': 'EMSPREMIUM',
        'c7df2760-2c81-4ef7-b578-5b5392b571df': 'ENTERPRISEPREMIUM',
        '87bbbc60-4754-4998-8c88-227dca264858': 'POWERAPPS_INDIVIDUAL_USER',
        '6470687e-a428-4b7a-bef2-8a291ad947c9': 'WINDOWS_STORE',
        '6fd2c87f-b296-42f0-b197-1e91e994b900': 'ENTERPRISEPACK',
        'f30db892-07e9-47e9-837c-80727f46fd3d': 'FLOW_FREE',
        '440eaaa8-b3e0-484b-a8be-62870b9ba70a': 'PHONESYSTEM_VIRTUALUSER',
        'bc946dac-7877-4271-b2f7-99d2db13cd2c': 'FORMS_PRO',
        'dcb1a3ae-b33f-4487-846a-a640262fadf4': 'POWERAPPS_VIRAL',
        '338148b6-1b11-4102-afb9-f92b6cdc0f8d': 'DYN365_ENTERPRISE_P1_IW',
        '6070a4c8-34c6-4937-8dfb-39bbc6397a60': 'MEETING_ROOM',
        'a403ebcc-fae0-4ca2-8c8c-7a907fd6c235': 'POWER_BI_STANDARD',
        '111046dd-295b-4d6d-9724-d52ac90bd1f2': 'WIN_DEF_ATP',
        '710779e8-3d4a-4c88-adb9-386c958d1fdf': 'TEAMS_EXPLORATORY',
        'efccb6f7-5641-4e0e-bd10-b4976e1bf68e': 'EMS',
        '90d8b3f8-712e-4f7b-aa1e-62e7ae6cbe96': 'SMB_APPS',
        'fcecd1f9-a91e-488d-a918-a96cdb6ce2b0': 'AX7_USER_TRIAL',
        '093e8d14-a334-43d9-93e3-30589a8b47d0': 'RMSBASIC',
        '53818b1b-4a27-454b-8896-0dba576410e6': 'PROJECTPROFESSIONAL',
        '18181a46-0d4e-45cd-891e-60aabd171b4e': 'STANDARDPACK',
    }
    for sku in skus:
        if sku in ms_licence_skus:
            dept_user.assigned_licences.append(ms_licence_skus[sku])
        else:
            dept_user.assigned_licences.append(sku)

    dept_user.save()


def deptuser_azure_sync(dept_user, container='azuread', azure_json='aadusers.json'):
    """Utility function to perform all of the steps to sync up a single DepartmentUser and Azure AD.
    Function may be run as-is, or queued as an asynchronous task.
    """
    azure_users = get_azure_users_json(container, azure_json)
    azure_user = find_user_in_list(azure_users, objectid=dept_user.azure_guid)

    if azure_user:
        update_deptuser_from_azure(azure_user, dept_user)
        dept_user.generate_ad_actions(azure_user)
        dept_user.audit_ad_actions(azure_user)


def get_photo_path(instance, filename='photo.jpg'):
    return os.path.join('user_photo', '{0}.{1}'.format(instance.id, os.path.splitext(filename)))


def get_photo_ad_path(instance, filename='photo.jpg'):
    return os.path.join('user_photo_ad', '{0}.{1}'.format(instance.id, os.path.splitext(filename)))


def convert_ad_timestamp(timestamp):
    """Converts an Active Directory timestamp to a Python datetime object.
    Ref: http://timestamp.ooz.ie/p/time-in-python.html
    """
    epoch_start = datetime(year=1601, month=1, day=1)
    seconds_since_epoch = timestamp / 10**7
    return epoch_start + timedelta(seconds=seconds_since_epoch)


def load_mugshots(data_dir='/root/mugshots'):
    from .models import DepartmentUser
    files = [x for x in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, x))]
    valid = 0
    for f in files:
        name = os.path.splitext(f)[0]
        qs = DepartmentUser.objects.filter(username__iexact=name)
        if qs:
            with open(os.path.join(data_dir, f)) as fp:
                qs[0].photo.save(f, ContentFile(fp.read()))
            print('Updated photo for {}'.format(name))
            valid += 1
        else:
            print('ERROR: Username {} not found'.format(name))

    print('{}/{} photos valid'.format(valid, len(files)))
