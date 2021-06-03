from django.conf import settings
from django.core.management.base import BaseCommand
from registers.models import ITSystem
from registers.utils_freshservice import get_freshservice_objects_curl, create_freshservice_object


class Command(BaseCommand):
    help = 'Syncs the IT System Register information to Freshservice'

    def handle(self, *args, **options):
        self.stdout.write('Querying Freshservice for IT Systems')
        it_systems_fs = get_freshservice_objects_curl(
            obj_type='assets',
            query='asset_type_id:{}'.format(settings.FRESHSERVICE_IT_SYSTEM_ASSET_TYPE_ID),
            verbose=True
        )
        if not it_systems_fs:
            self.stdout.write(self.style.ERROR('Freshservice API returned no IT System assets'))
            return

        self.stdout.write('Comparing Freshservice IT Systems to IT System Register')
        it_systems = ITSystem.objects.filter(status__in=[0, 2]).order_by('system_id')

        # Iterate through the list of IT Systems from the register.
        # If that system has a value for ``freshservice_api_url`` in its extra_data document,
        # assume that it has already been created within Freshservice and move on.
        # If not, check if there is a match (by name) in the IT System asset list from Freshservice.
        # If there is, link it.
        # If not, create a new asset in Freshservice and then link it.

        for system in it_systems:
            name = '{} - {}'.format(system.system_id, system.name)
            self.stdout.write('Checking {}'.format(name))

            if not system.extra_data:
                system.extra_data = {}
            if 'freshservice_api_url' not in system.extra_data:  # Not linked to a Freshservice object.
                # Is there already a matching asset in Freshservice?
                existing = False
                for asset in it_systems_fs:
                    system_id = asset['name'].split()[0]  # Match on System ID.
                    if system_id == system.system_id:
                        existing = True
                        url = '{}/assets/{}'.format(settings.FRESHSERVICE_ENDPOINT, asset['display_id'])
                        self.stdout.write('Linking {} to {}'.format(name, url))
                        system.extra_data['freshservice_api_url'] = url
                        system.save()
                        break  # Break out of the for loop.

                if not existing:
                    self.stdout.write('Unable to find {} in Freshservice, creating a new asset there'.format(name))
                    data = {
                        'asset_type_id': settings.FRESHSERVICE_IT_SYSTEM_ASSET_TYPE_ID,
                        'name': name,
                    }
                    asset = create_freshservice_object('assets', data).json()['asset']
                    url = '{}/assets/{}'.format(settings.FRESHSERVICE_ENDPOINT, asset['display_id'])
                    self.stdout.write('Linking {} to {}'.format(name, url))
                    system.extra_data['freshservice_api_url'] = url
                    system.save()

        self.stdout.write(self.style.SUCCESS('Completed'))
