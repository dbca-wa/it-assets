from data_storage import AzureBlobStorage
from datetime import datetime, timedelta
from dbca_utils.utils import env
from django.conf import settings
from django.core.files.base import ContentFile
import json
import logging
import os
import re
import subprocess


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
    dept_user.assigned_licences = [re.search(licence_pattern, i)[0] for i in azure_user['AssignedLicenses'] if re.search(licence_pattern, i)]
    # dept_user.proxy_addresses = [i.lower().replace('smtp:', '') for i in azure_user['ProxyAddresses'] if i.lower().startswith('smtp')]
    dept_user.mail_nickname = azure_user['MailNickName']
    dept_user.save()


# Python 2 can't serialize unbound functions, so here's some dumb glue
def get_photo_path(instance, filename='photo.jpg'):
    return os.path.join('user_photo', '{0}.{1}'.format(instance.id, os.path.splitext(filename)))


def get_photo_ad_path(instance, filename='photo.jpg'):
    return os.path.join('user_photo_ad', '{0}.{1}'.format(instance.id, os.path.splitext(filename)))


def logger_setup(name):
    # Ensure that the logs dir is present.
    subprocess.check_call(['mkdir', '-p', 'logs'])
    # Set up logging in a standardised way.
    logger = logging.getLogger(name)
    if settings.DEBUG:
        logger.setLevel(logging.DEBUG)
    else:  # Log at a higher level when not in debug mode.
        logger.setLevel(logging.INFO)
    if not len(logger.handlers):  # Avoid creating duplicate handlers.
        fh = logging.handlers.RotatingFileHandler(
            'logs/{}.log'.format(name), maxBytes=5 * 1024 * 1024, backupCount=5)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger


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
