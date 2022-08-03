from django.core.management.base import BaseCommand
from itassets.utils_freshservice import get_freshservice_objects, create_freshservice_object, update_freshservice_object
import logging
from organisation.utils import ms_graph_users


class Command(BaseCommand):
    help = 'Syncs department user information to Freshservice'

    def handle(self, *args, **options):
        logger = logging.getLogger('organisation')
        logger.info('Querying Freshservice for requesters')
        requesters_fs = get_freshservice_objects(obj_type='requesters')
        requesters_fs = {r['primary_email']: r for r in requesters_fs}
        logger.info('Querying Freshservice for agents')
        agents_fs = get_freshservice_objects(obj_type='agents')
        agents_fs = {r['email']: r for r in agents_fs}
        logger.info('Querying Freshservice for departments')
        departments_fs = get_freshservice_objects(obj_type='departments')
        departments_fs = {d['name']: d for d in departments_fs}

        if not requesters_fs:
            logger.error('Freshservice API returned no requesters')
            return

        logger.info('Querying Microsoft Graph API for Azure AD users.')
        azure_users = ms_graph_users(licensed=True)

        if not azure_users:
            logger.error('Microsoft Graph API returned no users')
            return

        # Iterate through the list of Azure AD users.
        # Check if there is a match (by email) in the requester list from Freshservice.
        # If there is, check for any updates.
        # If not, create a new requester in Freshservice.

        for user in azure_users:
            # Some licensed service accounts exist, but have no first/last name. Skip these.
            if not user['givenName'] and not user['surname']:
                continue

            # Skip disabled Azure AD accounts.
            if not user['accountEnabled']:
                continue

            # Is there already a matching requester in Freshservice?
            if user['mail'].lower() in requesters_fs:
                requester = requesters_fs[user['mail'].lower()]
            else:
                requester = None
            # Is there already a matching agent in Freshservice?
            if user['mail'].lower() in agents_fs:
                agent = agents_fs[user['mail'].lower()]
            else:
                agent = None

            # Telephone: for 'numbers' which consist of one or more spaces, change these to None in-place.
            if user['telephoneNumber'] and not user['telephoneNumber'].strip():
                user['telephoneNumber'] = None

            if requester:  # Freshservice requester exists, check for any updates.
                data = {}
                if requester['first_name'] and requester['first_name'] != user['givenName']:
                    data['first_name'] = user['givenName']
                    logger.info('Updating requester {} first_name to {}'.format(requester['primary_email'], user['givenName']))
                if requester['last_name'] and requester['last_name'] != user['surname']:
                    data['last_name'] = user['surname']
                    logger.info('Updating requester {} last_name to {}'.format(requester['primary_email'], user['surname']))
                if user['jobTitle'] and requester['job_title'] != user['jobTitle']:
                    data['job_title'] = user['jobTitle']
                    logger.info('Updating requester {} job_title to {}'.format(requester['primary_email'], user['jobTitle']))
                if user['telephoneNumber'] and requester['work_phone_number'] != user['telephoneNumber']:
                    data['work_phone_number'] = user['telephoneNumber']
                    logger.info('Updating requester {} work_phone_number to {}'.format(requester['primary_email'], user['telephoneNumber']))
                # Freshservice requester department - this is a bit different to the fields above.
                # We use this to record the requester cost centre.
                if user['companyName'] and user['companyName'] in departments_fs:
                    dept = departments_fs[user['companyName']]
                    if dept['id'] not in requester['department_ids']:
                        data['department_ids'] = [dept['id']]
                if data:
                    # Update the Freshservice requester.
                    resp = update_freshservice_object('requesters', requester['id'], data)
            elif agent:
                data = {}
                if user['givenName'] and agent['first_name'] != user['givenName']:
                    data['first_name'] = user['givenName']
                    logger.info('Updating agent {} first_name to {}'.format(agent['email'], user['givenName']))
                if user['surname'] and agent['last_name'] != user['surname']:
                    data['last_name'] = user['surname']
                    logger.info('Updating agent {} last_name to {}'.format(agent['email'], user['surname']))
                if user['jobTitle'] and agent['job_title'] != user['jobTitle']:
                    data['job_title'] = user['jobTitle']
                    logger.info('Updating agent {} job_title to {}'.format(agent['email'], user['jobTitle']))
                if user['telephoneNumber'] and agent['work_phone_number'] != user['telephoneNumber']:
                    data['work_phone_number'] = user['telephoneNumber']
                    logger.info('Updating agent {} work_phone_number to {}'.format(agent['email'], user['telephoneNumber']))
                # Freshservice agent department - this is a bit different to the fields above.
                # We use this to record the agent cost centre.
                if user['companyName'] and user['companyName'] in departments_fs:
                    dept = departments_fs[user['companyName']]
                    if dept['id'] not in agent['department_ids']:
                        data['department_ids'] = [dept['id']]
                if data:
                    # Update the Freshservice agent.
                    resp = update_freshservice_object('agents', agent['id'], data)
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

                logger.info('Unable to find {} in Freshservice, creating a new requester'.format(user['mail']))
                resp = create_freshservice_object('requesters', data)
                if resp.status_code == 409:
                    logger.info('Skipping {} (probably an agent)'.format(user['mail']))
