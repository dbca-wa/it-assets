from django.conf import settings
from django.core.management.base import BaseCommand
import logging
import requests
from urllib.parse import urlparse
from itassets.utils_freshservice import get_freshservice_objects_curl, create_freshservice_object, update_freshservice_object, FRESHSERVICE_AUTH
from registers.models import ITSystem


class Command(BaseCommand):
    help = 'Syncs the IT System Register information to Freshservice'

    def handle(self, *args, **options):
        logger = logging.getLogger('itassets')
        logger.info('Querying Freshservice for IT Systems')
        it_systems_fs = get_freshservice_objects_curl(
            obj_type='assets',
            query='asset_type_id:{}'.format(settings.FRESHSERVICE_IT_SYSTEM_ASSET_TYPE_ID),
        )
        if not it_systems_fs:
            logger.error('Freshservice API returned no IT System assets')
            return

        logger.info('Comparing Freshservice IT Systems to IT System Register')
        it_systems = ITSystem.objects.filter(status__in=[0, 2]).order_by('system_id')

        # Iterate through the list of IT Systems from the register.
        # If that system has a value for ``freshservice_api_url`` in its extra_data document,
        # assume that it has already been created within Freshservice and check if updates are needed.
        # If not, check if there is a match (by name) in the IT System asset list from Freshservice.
        # If there is, link it.
        # If not, create a new asset in Freshservice and then link it.

        for system in it_systems:
            name = '{} - {}'.format(system.system_id, system.name)
            if urlparse(system.link) and urlparse(system.link).scheme:
                link = system.link
            else:
                link = None
            logger.info('Checking {}'.format(name))

            if not system.extra_data:
                system.extra_data = {}
            if 'freshservice_api_url' not in system.extra_data:  # IT System is not linked to any Freshservice asset.
                # Is there already a matching asset in Freshservice?
                existing = False
                for asset in it_systems_fs:
                    asset_system_id = asset['name'].split()[0]  # Match on System ID.
                    if asset_system_id == system.system_id:
                        # Link the IT System to this Freshservice asset.
                        existing = True
                        url = '{}/assets/{}'.format(settings.FRESHSERVICE_ENDPOINT, asset['display_id'])
                        logger.info('Linking {} to {}'.format(name, url))
                        system.extra_data['freshservice_api_url'] = url
                        system.save()
                        break  # Break out of the for loop.

                if not existing:
                    logger.info('Unable to find {} in Freshservice, creating a new asset'.format(name))
                    data = {
                        'asset_type_id': settings.FRESHSERVICE_IT_SYSTEM_ASSET_TYPE_ID,
                        'name': name,
                    }
                    # type_field values cannot be blank or None.
                    type_fields = {}
                    if link:
                        type_fields['link_75000295285'] = link
                    if system.owner:
                        type_fields['system_owner_75000295285'] = system.owner.name
                    if system.technology_custodian:
                        type_fields['technology_custodian_75000295285'] = system.technology_custodian.name
                    if system.information_custodian:
                        type_fields['information_custodian_75000295285'] = system.information_custodian.name
                    if type_fields:
                        data['type_fields'] = type_fields

                    resp = create_freshservice_object('assets', data)
                    asset = resp.json()['asset']
                    url = '{}/assets/{}'.format(settings.FRESHSERVICE_ENDPOINT, asset['display_id'])
                    logger.info('Linking {} to {}'.format(name, url))
                    system.extra_data['freshservice_api_url'] = url
                    system.save()
            else:  # IT System is linked to an existing Freshservice asset.
                matched = False
                # Find the matching asset.
                display_id = int(system.extra_data['freshservice_api_url'].split('/')[-1])
                for asset in it_systems_fs:
                    if asset['display_id'] == display_id:
                        matched = True
                        # Check if updates are required.
                        # Compare the Freshservice asset to the IT System to check for updates.
                        data = {}
                        type_fields = {}
                        if asset['name'] != name:
                            data['name'] = name
                        if link and asset['type_fields']['link_75000295285'] != link:
                            type_fields['link_75000295285'] = link
                        if system.owner and asset['type_fields']['system_owner_75000295285'] != system.owner.name:
                            type_fields['system_owner_75000295285'] = system.owner.name
                        if system.technology_custodian and asset['type_fields']['technology_custodian_75000295285'] != system.technology_custodian.name:
                            type_fields['technology_custodian_75000295285'] = system.technology_custodian.name
                        if system.information_custodian and asset['type_fields']['information_custodian_75000295285'] != system.information_custodian.name:
                            type_fields['information_custodian_75000295285'] = system.information_custodian.name

                        # Did any of the asset's type_fields need to be updated?
                        if type_fields:
                            data['type_fields'] = type_fields
                        if data:
                            # Update the Freshservice asset.
                            resp = update_freshservice_object('assets', asset['display_id'], data)
                            logger.info('Updated details for {} ({})'.format(system.extra_data['freshservice_api_url'], data))

                        break  # Break out of the for loop.

                if not matched:
                    # We may be in the situation where the IT System is "linked" to a non-existent Freshservice asset.
                    # Alternatively, the Freshservice API sometimes seems to not return all of the systems :|
                    # Try manually downloading the linked asset first.
                    logger.info(self.style.WARNING('Asset not matched in list, trying to download manually at {}'.format(system.extra_data['freshservice_api_url'])))
                    params = {'include': 'type_fields'}
                    resp = requests.get(system.extra_data['freshservice_api_url'], auth=FRESHSERVICE_AUTH, params=params)
                    resp.raise_for_status()
                    asset = resp.json()['asset']
                    asset_system_id = asset['name'].split()[0]  # Match on System ID.
                    if asset_system_id == system.system_id:
                        # Finally, we have a match. Check if updates are required.
                        data = {}
                        type_fields = {}
                        if asset['name'] != name:
                            data['name'] = name
                        if link and asset['type_fields']['link_75000295285'] != link:
                            type_fields['link_75000295285'] = link
                        if system.owner and asset['type_fields']['system_owner_75000295285'] != system.owner.name:
                            type_fields['system_owner_75000295285'] = system.owner.name
                        if system.technology_custodian and asset['type_fields']['technology_custodian_75000295285'] != system.technology_custodian.name:
                            type_fields['technology_custodian_75000295285'] = system.technology_custodian.name
                        if system.information_custodian and asset['type_fields']['information_custodian_75000295285'] != system.information_custodian.name:
                            type_fields['information_custodian_75000295285'] = system.information_custodian.name

                        # Did any of the asset's type_fields need to be updated?
                        if type_fields:
                            data['type_fields'] = type_fields
                        if data:
                            # Update the Freshservice asset.
                            resp = update_freshservice_object('assets', asset['display_id'], data)
                            logger.info('Updated details for {} ({})'.format(system.extra_data['freshservice_api_url'], data))
                    else:
                        logger.error('{} is linked to the wrong Freshservice asset {}'.format(name, system.extra_data['freshservice_api_url']))
                        system.extra_data.pop('freshservice_api_url')
                        system.save()

        logger.info('Completed')
