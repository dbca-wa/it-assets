import json
import os

from .models import Computer
from .utils import logger_setup


def salt_load_computers():
    """Update the database with Computer information from Salt (minions).
    """
    logger = logger_setup('salt_load_computers')
    logger_ex = logger_setup('exceptions_salt_load_computers')
    grains_path = os.environ.get('SALT_GRAINS_PATH')
    num_created = 0
    num_updated = 0
    num_errors = 0

    for i in [f for f in os.listdir(grains_path) if f.endswith('.json')]:
        try:
            path = os.path.join(grains_path, i)
            data = json.loads(open(path).read())
            # data should be a dict with one key (hostname).
            host = list(data.keys())[0]
            host_info = data[host]

            try:
                computer = Computer.objects.get(hostname=host)
                num_updated += 1
                logger.info('Computer {} updated from Salt'.format(computer))
            except Computer.DoesNotExist:
                logger.info('No match for Computer object with hostname {}; creating new object'.format(host))
                computer = Computer(hostname=host)
                num_created += 1
                pass

            computer.domain_bound = True
            if 'productname' in host_info:
                computer.model = host_info['productname']
            if 'serialnumber' in host_info:
                computer.serial_number = host_info['serialnumber']
            if 'os' in host_info:
                computer.os_name = host_info['os']
            if 'osrelease' in host_info:
                computer.os_version = host_info['osrelease']
            if 'osarch' in host_info:
                computer.os_arch = host_info['osarch']
            computer.save()

        except Exception as e:
            logger_ex.error('Error while loading computer from Salt')
            logger_ex.info(data)
            logger_ex.exception(e)
            num_errors += 1
            continue

    logger.info('Created {}, updated {}, errors {}'.format(num_created, num_updated, num_errors))
