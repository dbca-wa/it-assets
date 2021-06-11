from django.core.management.base import BaseCommand
from itassets.utils_freshservice import get_freshservice_objects, create_freshservice_object, update_freshservice_object
from organisation.utils import ms_graph_users


class Command(BaseCommand):
    help = 'Syncs department user information to Freshservice'

    def handle(self, *args, **options):
        self.stdout.write('Querying Freshservice for requesters')
        requesters_fs = get_freshservice_objects(obj_type='requesters')

        if not requesters_fs:
            self.stdout.write(self.style.ERROR('Freshservice API returned no requesters'))
            return

        self.stdout.write('Querying Microsoft Graph API for Azure AD users.')
        azure_users = ms_graph_users(licensed=True)

        if not azure_users:
            self.stdout.write(self.style.ERROR('Microsoft Graph API returned no users'))
            return

        # Iterate through the list of Azure AD users.
        # Check if there is a match (by email) in the requester list from Freshservice.
        # If there is, check for any updates.
        # If not, create a new requester in Freshservice.

        for user in azure_users:
            # Some licensed service accounts exist, but have no first/last name. Skip these.
            if not user['givenName'] and not user['surname']:
                continue

            # Is there already a matching requester in Freshservice?
            existing = False
            for req in requesters_fs:
                if req['primary_email'].lower() == user['mail'].lower():
                    existing = req
                    break  # Break out of the for loop.

            if not existing:
                data = {
                    'primary_email': user['mail'].lower(),
                    'first_name': user['givenName'],
                    'last_name': user['surname'],
                    'job_title': user['jobTitle'] if user['jobTitle'] else '',
                    'work_phone_number': user['telephoneNumber'] if user['telephoneNumber'] else '',
                }
                self.stdout.write('Unable to find {} in Freshservice, creating a new requester'.format(user['mail']))
                resp = create_freshservice_object('requesters', data)
                if resp.status_code == 409:
                    self.stdout.write(self.style.WARNING('Skipping {} (probably an agent)'.format(user['mail'])))
                elif resp.status_code == 201:
                    resp.raise_for_status()
            else:  # Freshservice requester exists, check for any updates.
                data = {}
                if existing['first_name'] != user['givenName']:
                    data['first_name'] = user['givenName']
                    self.stdout.write('Updating requester {} first_name to {}'.format(existing['primary_email'], user['givenName']))
                if existing['last_name'] != user['surname']:
                    data['last_name'] = user['surname']
                    self.stdout.write('Updating requester {} last_name to {}'.format(existing['primary_email'], user['surname']))
                if existing['job_title'] != user['jobTitle']:
                    data['job_title'] = user['jobTitle']
                    self.stdout.write('Updating requester {} job_title to {}'.format(existing['primary_email'], user['jobTitle']))
                if user['telephoneNumber'] and existing['work_phone_number'] != user['telephoneNumber']:
                    data['work_phone_number'] = user['telephoneNumber']
                    self.stdout.write('Updating requester {} work_phone_number to {}'.format(existing['primary_email'], user['telephoneNumber']))
                if data:
                    # Update the Freshservice requester.
                    resp = update_freshservice_object('requesters', existing['id'], data)
                    resp.raise_for_status()
                    self.stdout.write('Updated Freshdesk requester {}'.format(existing['primary_email']))

        self.stdout.write(self.style.SUCCESS('Completed'))
