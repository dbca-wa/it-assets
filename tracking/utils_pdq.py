from datetime import datetime
from django.utils import timezone
from django.db.models import Count
import logging
import os
import re
import unicodecsv
import pytz
from uuid import UUID
from .models import Computer
from assets.models import HardwareAsset
from organisation.models import DepartmentUser

LOGGER = logging.getLogger('sync_tasks')

perth = pytz.timezone('Australia/Perth')

def csv_data(csv_path, skip_header=True):
    """Pass in the path to a CSV file, returns a CSV Reader object.
    """
    csv_file = open(csv_path, 'rb')
    data = unicodecsv.reader(csv_file)
    if skip_header:
        try:  # Python 3+
            next(data)
        except:  # Python 2.7
            data.next()
    return data


def pdq_scrub_duplicate_computers():
    # scrub duplicate serial numbers for Dell and MS
    serial_re = re.compile('^([0-9]{12}|[A-Z0-9]{7})$')
    for computer in Computer.objects.filter(serial_number__isnull=False):
        if serial_re.search(computer.serial_number):
            hw = HardwareAsset.objects.filter(serial=computer.serial_number).first()
            if hw:
                hw.tracked_computer = computer
                hw.save()
                computer.cost_centre = hw.cost_centre
                computer.save()


    serial_chk = Computer.objects.values_list('serial_number').filter(serial_number__isnull=False).exclude(serial_number="").annotate(Count('serial_number')).filter(serial_number__count__gt=1)
    for serial, _ in serial_chk:
        if serial_re.search(serial):
            serial_qs = Computer.objects.filter(serial_number=serial).order_by('-date_updated')
            new_comp = serial_qs[0]
            for dead_comp in serial_qs[1:]:
                LOGGER.info('Computer {} has a duplicate serial number of computer {}, deleting'.format(dead_comp, new_comp))
                dead_comp.delete()


def pdq_load_computers():
    """Update the database with Computer information from PDQ Inventory.
    """
    update_time = timezone.now()

    csv_path = os.path.join(os.environ.get('PDQ_INV_PATH'), 'pdq_computers_max.csv')
    data = csv_data(csv_path)
    num_created = 0
    num_updated = 0
    num_errors = 0

    csv_path = os.path.join(os.environ.get('PDQ_INV_PATH'), 'pdq_computers_logins.csv')
    logins = [x for x in csv_data(csv_path)]


    for i, row in enumerate(data):
        try:
            computer = None
            try:
                urn = UUID(row[2]).urn
            except Exception as e:
                LOGGER.error('Computer {} has invalid Active Directory GUID in PDQ Inventory {}, skipping.'.format(row[1], row[2]))
                LOGGER.info(row)
                LOGGER.exception(e)
                num_errors += 1
                continue

            # First, try and match AD GUID.
            if urn and row[2]:
                try:
                    computer = Computer.objects.get(ad_guid=urn)
                    # check for clashing AD DN
                    if row[3]:
                        try:
                            dn = Computer.objects.get(ad_dn=row[3])
                            if dn.pk != computer.pk:
                                dn.ad_dn = None
                                dn.save()
                        except Computer.DoesNotExist:
                            pass

                    num_updated += 1
                except Computer.DoesNotExist:
                    pass
            # Second, try and match AD DN.
            if computer is None and row[3]:
                try:
                    computer = Computer.objects.get(ad_dn=row[3])
                    num_updated += 1
                except Computer.DoesNotExist:
                    pass
            # Last, try to match via sAMAccountName. If no match, skip the record.
            if computer is None:
                sam = '{}$'.format(row[1].upper())
                try:
                    computer = Computer.objects.get(sam_account_name=sam)
                    num_updated += 1
                except Computer.DoesNotExist:
                    LOGGER.info('No match for Computer object with SAM ID {} creating new object'.format(sam))
                    computer = Computer(sam_account_name=sam)
                    num_created += 1
                    pass

            computer.domain_bound = True
            computer.ad_guid = urn
            computer.ad_dn = row[3]
            computer.manufacturer = row[5]
            computer.model = row[6]
            computer.chassis = row[7]
            computer.serial_number = row[8]
            computer.os_name = row[9]
            computer.os_version = row[10]
            computer.os_service_pack = row[11]
            computer.os_arch = row[12]
            computer.memory = row[13]
            computer.hostname = row[14]
            computer.date_pdq_updated = update_time
            
            if row[16]:
                computer.date_ad_created = perth.localize(datetime.strptime(row[16], '%Y-%m-%d %H:%M:%S'))
            if logins[i][1]:
                computer.last_ad_login_date = perth.localize(datetime.strptime(logins[i][1], '%Y-%m-%d %H:%M:%S'))
            if logins[i][2]:
                computer.last_ad_login_username = logins[i][2]
            if logins[i][3]:
                user = DepartmentUser.objects.filter(ad_dn=logins[i][3]).first()
                if user:
                    computer.last_login = user
            if row[19]:
                computer.date_pdq_last_seen = perth.localize(datetime.strptime(row[19], '%Y-%m-%d %H:%M:%S'))

            computer.save()
            hw = None
            if not hw and len( computer.serial_number ) > 3:
                hw = HardwareAsset.objects.filter(serial=computer.serial_number).first()
            if not hw and row[15].startswith('IT'): # BiosAssetTag
                hw = HardwareAsset.objects.filter(asset_tag=row[15]).first()
            if hw:
                hw.tracked_computer = computer
                hw.save()
                computer.cost_centre = hw.cost_centre
                computer.save()

            LOGGER.info('Computer {} updated from PDQ Inventory scan data'.format(computer))
        except Exception as e:
            LOGGER.error('Error while loading computers from PDQ')
            LOGGER.info(row)
            LOGGER.exception(e)
            num_errors += 1
            continue

    LOGGER.info('Created {}, updated {}, errors {}'.format(num_created, num_updated, num_errors))
