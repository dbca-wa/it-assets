from django.core.management.base import BaseCommand
from itassets.utils_freshservice import get_freshservice_objects, create_freshservice_object, update_freshservice_object
from organisation.utils import ms_graph_users


class Command(BaseCommand):
    help = 'Syncs department user information to Freshservice'

    def handle(self, *args, **options):
        self.stdout.write('Querying Freshservice for requesters')
        requesters_fs = get_freshservice_objects(obj_type='requesters')
        requesters_fs = {r['primary_email']: r for r in requesters_fs}
        departments_fs = get_freshservice_objects(obj_type='departments')
        departments_fs = {d['name']: d for d in departments_fs}

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
            if user['mail'].lower() in requesters_fs:
                requester = requesters_fs[user['mail'].lower()]

            if requester:  # Freshservice requester exists, check for any updates.
                data = {}

                if requester['first_name'] != user['givenName']:
                    data['first_name'] = user['givenName']
                    self.stdout.write('Updating requester {} first_name to {}'.format(requester['primary_email'], user['givenName']))
                if requester['last_name'] != user['surname']:
                    data['last_name'] = user['surname']
                    self.stdout.write('Updating requester {} last_name to {}'.format(requester['primary_email'], user['surname']))
                if requester['job_title'] != user['jobTitle']:
                    data['job_title'] = user['jobTitle']
                    self.stdout.write('Updating requester {} job_title to {}'.format(requester['primary_email'], user['jobTitle']))
                if user['telephoneNumber'] and requester['work_phone_number'] != user['telephoneNumber']:
                    data['work_phone_number'] = user['telephoneNumber']
                    self.stdout.write('Updating requester {} work_phone_number to {}'.format(requester['primary_email'], user['telephoneNumber']))
                # Freshservice requester department - this is a bit different to the fields above.
                # We use this to record the requester cost centre.
                if user['companyName'] and user['companyName'] in departments_fs:
                    dept = departments_fs[user['companyName']]
                    if dept['id'] not in requester['department_ids']:
                        data['department_ids'] = [dept['id']]

                if data:
                    # Update the Freshservice requester.
                    resp = update_freshservice_object('requesters', requester['id'], data)
                    resp.raise_for_status()
                    self.stdout.write('Updated Freshdesk requester {}'.format(requester['primary_email']))
            else:
                data = {
                    'primary_email': user['mail'].lower(),
                    'first_name': user['givenName'],
                    'last_name': user['surname'],
                    'job_title': user['jobTitle'] if user['jobTitle'] else '',
                    'work_phone_number': user['telephoneNumber'] if user['telephoneNumber'] else '',
                }
                if user['companyName'] and user['companyName'] in departments_fs:
                    dept = departments_fs[user['companyName']]
                    data['department_ids'] = [dept['id']]

                self.stdout.write('Unable to find {} in Freshservice, creating a new requester'.format(user['mail']))
                resp = create_freshservice_object('requesters', data)
                if resp.status_code == 409:
                    self.stdout.write(self.style.WARNING('Skipping {} (probably an agent)'.format(user['mail'])))
                elif resp.status_code == 201:
                    resp.raise_for_status()

        self.stdout.write(self.style.SUCCESS('Completed'))
