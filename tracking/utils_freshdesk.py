from dateutil.parser import parse
from django.conf import settings
import logging
import requests
from requests.exceptions import HTTPError
from tracking.models import DepartmentUser, FreshdeskTicket, FreshdeskConversation, FreshdeskContact


HEADERS_JSON = {'Content-Type': 'application/json'}
FRESHDESK_AUTH = (settings.FRESHDESK_API_KEY, 'X')
LOGGER = logging.getLogger('sync_tasks')


def get_freshdesk_object(obj_type, id):
    """Query the Freshdesk v2 API for a single object.
    """
    url = settings.FRESHDESK_ENDPOINT + '/{}/{}'.format(obj_type, id)
    r = requests.get(url, auth=FRESHDESK_AUTH)
    if not r.status_code == 200:
        r.raise_for_status()
    return r.json()


def update_freshdesk_object(obj_type, data, id=None):
    """Use the Freshdesk v2 API to create or update an object.
    Accepts an object name (string), a dict of fields, and an optional object
    ID for updates to existing objects.
    Ref: https://developer.freshdesk.com/api/#create_contact
    """
    if not id:  # Assume creation of new object.
        url = settings.FRESHDESK_ENDPOINT + '/{}'.format(obj_type)
        r = requests.post(url, auth=FRESHDESK_AUTH, json=data)
    else:  # Update an existing object.
        url = settings.FRESHDESK_ENDPOINT + '/{}/{}'.format(obj_type, id)
        r = requests.put(url, auth=FRESHDESK_AUTH, json=data)
    return r  # Return the response, so we can handle non-200 gracefully.


def get_freshdesk_objects(obj_type, progress=True, limit=False, params={}):
    """Query the Freshdesk v2 API for all objects of a defined type.
    ``limit`` should be an integer (maximum number of objects to return).
    May take some time, depending on the number of objects.
    """
    url = settings.FRESHDESK_ENDPOINT + '/{}'.format(obj_type)
    if 'page' not in params:
        params['page'] = 1
    if 'per_page' not in params:
        params['per_page'] = 100
    objects = []
    further_results = True

    while further_results:
        if progress:
            print('Querying page {}'.format(params['page']))

        r = requests.get(url, auth=FRESHDESK_AUTH, params=params)
        if not r.status_code == 200:
            r.raise_for_status()

        if 'link' not in r.headers:  # No further paginated results.
            further_results = False
            if progress:
                print('Done!')

        objects.extend(r.json())
        params['page'] += 1

        if limit and len(objects) >= limit:
            further_results = False
            objects = objects[:limit]

    # Return the full list of objects returned.
    return objects


def freshdesk_sync_contacts(contacts=None, companies=None, agents=None):
    """Iterate through all DepartmentUser objects, and ensure that each user's
    information is synced correctly to a Freshdesk contact.
    May optionally be passed in dicts of contacts & companies.
    """
    try:
        if not contacts:
            LOGGER.info('Querying Freshdesk for current contacts')
            contacts = get_freshdesk_objects(obj_type='contacts', progress=False, params={'page': 1})
            contacts = {c['email'].lower(): c for c in contacts if c['email']}
        if not companies:
            LOGGER.info('Querying Freshdesk for current companies')
            companies = get_freshdesk_objects(obj_type='companies', progress=False, params={'page': 1})
            companies = {c['name']: c for c in companies}
        # FIXME: ignore Agents for the time being.
        #if not agents:
        #    LOGGER.info('Querying Freshdesk for current agents')
        #    agents = get_freshdesk_objects(obj_type='agents', progress=False, params={'page': 1})
        #    agents = {a['contact']['email'].lower(): a['contact'] for a in agents if a['contact']['email']}
    except Exception as e:
        LOGGER.exception(e)
        return False

    # Filter DepartmentUsers: valid email (contains @), not -admin, DN contains 'OU=Users', active
    d_users = DepartmentUser.objects.filter(email__contains='@', ad_dn__contains='OU=Users', active=True).exclude(email__contains='-admin')
    LOGGER.info('Syncing details for {} DepartmentUsers to Freshdesk'.format(d_users.count()))
    for user in d_users:
        if user.email.lower() in contacts:
            # The DepartmentUser exists in Freshdesk; verify and update details.
            fd = contacts[user.email.lower()]
            data = {}
            user_sync = False
            # use extra attributes from org_data, if available
            cost_centre = user.org_data.get('cost_centre', {}).get('code', '') if user.org_data else None
            try:
                cost_centre = int(cost_centre)  # The cost_centre custom field in FD must be an integer.
            except:
                cost_centre = None
            physical_location = user.org_data.get('location', {}).get('name', '') if user.org_data else None
            department = user.org_data.get('units', []) if user.org_data else []
            department = department[0].get('name', '') if len(department) > 0 else None
            changes = []

            if user.name != fd['name']:
                user_sync = True
                data['name'] = user.name
                changes.append('name')
            if user.telephone != fd['phone']:
                user_sync = True
                data['phone'] = user.telephone
                changes.append('phone')
            if user.title != fd['job_title']:
                user_sync = True
                data['job_title'] = user.title
                changes.append('job_title')
            if department and department in companies and fd['company_id'] != companies[department]['id']:
                user_sync = True
                data['company_id'] = companies[department]['id']
                changes.append('company_id')
            # Custom fields in Freshdesk: Cost Centre no.
            if 'custom_fields' in fd:  # Field may not exist in the API obj.
                if cost_centre and fd['custom_fields']['cost_centre'] != cost_centre:
                    user_sync = True
                    data['custom_fields'] = {'cost_centre': cost_centre}
                    changes.append('cost_centre')
                # Custom fields in Freshdesk: Physical location
                if physical_location and fd['custom_fields']['location'] != physical_location:
                    user_sync = True
                    if 'custom_fields' in data:
                        data['custom_fields']['location'] = physical_location
                    else:
                        data['custom_fields'] = {'location': physical_location}
                    changes.append('physical_location')
            if user_sync:  # Sync user details to their Freshdesk contact.
                r = update_freshdesk_object('contacts', data, fd['id'])
                if r.status_code == 403:  # Forbidden
                    # A 403 response probably means that we hit the API throttle limit.
                    # Abort the synchronisation.
                    LOGGER.error('HTTP403 received from Freshdesk API, aborting')
                    return False
                LOGGER.info('{} was updated in Freshdesk (status {}), changed: {}'.format(
                    user.email.lower(), r.status_code, ', '.join(changes)))
        #elif user.email.lower() in agents:
        #    # The DepartmentUser is an agent; skip (can't update Agent details via the API).
        #    LOGGER.info('{} is an agent, skipping sync'.format(user.email.lower()))
        #    continue
        #    # The DepartmentUser does not exist in Freshdesk; create them as a Contact.
        else:
            data = {'name': user.name, 'email': user.email.lower(),
                    'phone': user.telephone, 'job_title': user.title}
            department = user.org_data.get('units', []) if user.org_data else []
            department = department[0].get('name', '') if len(department) > 0 else None
            if department and department in companies:
                data['company_id'] = companies[department]['id']
            r = update_freshdesk_object('contacts', data)
            if not r.status_code == 200:  # Error, unable to process request.
                LOGGER.warn('{} not created in Freshdesk (status {})'.format(user.email.lower(), r.status_code))
            else:
                LOGGER.info('{} created in Freshdesk (status {})'.format(user.email.lower(), r.status_code))

    return True


def freshdesk_cache_agents():
    """DEPRECATED: no longer caching Freshdesk agents at present.
    Cache a list of Freshdesk agents as contacts, as the API treats Agents
    differently to Contacts.
    """
    agents = get_freshdesk_objects(obj_type='agents', progress=False, params={'page': 1})
    for i in agents:
        data = i['contact']
        data['contact_id'] = i['id']
        data['created_at'] = parse(data['created_at'])
        data['updated_at'] = parse(data['updated_at'])
        data.pop('last_login_at', None)
        fc, create = FreshdeskContact.objects.update_or_create(contact_id=data['contact_id'], defaults=data)
        if create:
            LOGGER.info('{} created'.format(fc))
        else:
            LOGGER.info('{} updated'.format(fc))
        # Attempt to match with a DepartmentUser.
        fc.match_dept_user()


def freshdesk_cache_tickets(tickets=None):
    """Cache passed-in list of Freshdesk tickets in the database. If no tickets
    are passed in, query the API for the newest tickets.
    """
    if not tickets:
        try:
            LOGGER.info('Querying Freshdesk for current tickets')
            tickets = get_freshdesk_objects(obj_type='tickets', progress=False, limit=30, params={'page': 1})
        except Exception as e:
            LOGGER.exception(e)
            return False

    # Map the Freshdesk ticket API return to our internal model for caching.
    # This needs to be fairly explicit to account for the API response evolving :|
    mapped_tickets = []
    for t in tickets:
        t2 = {}
        t2['cc_emails'] = t['cc_emails']
        t2['created_at'] = parse(t['created_at'])
        t2['custom_fields'] = t['custom_fields']
        t2['due_by'] = parse(t['due_by'])
        t2['fr_due_by'] = parse(t['fr_due_by'])
        t2['fr_escalated'] = t['fr_escalated']
        t2['fwd_emails'] = t['fwd_emails']
        t2['group_id'] = t['group_id']
        t2['is_escalated'] = t['is_escalated']
        t2['priority'] = t['priority']
        t2['reply_cc_emails'] = t['reply_cc_emails']
        t2['requester_id'] = t['requester_id']
        t2['responder_id'] = t['responder_id']
        t2['spam'] = t['spam']
        t2['status'] = t['status']
        t2['subject'] = t['subject']
        t2['tags'] = t['tags']
        t2['ticket_id'] = t['id']
        t2['to_emails'] = t['to_emails']
        t2['type'] = t['type']
        t2['updated_at'] = parse(t['updated_at'])
        mapped_tickets.append(t2)

    created, updated = 0, 0
    contact_keys = [i.name for i in FreshdeskContact._meta.fields]
    conv_keys = [i.name for i in FreshdeskConversation._meta.fields]
    # Iterate through mapped_tickets; determine if a cached FreshdeskTicket should be
    # created or updated.
    for t in mapped_tickets:
        try:
            ft, create = FreshdeskTicket.objects.update_or_create(ticket_id=t['ticket_id'], defaults=t)
            if create:
                LOGGER.info('{} created'.format(ft))
                created += 1
            else:
                LOGGER.info('{} updated'.format(ft))
                updated += 1
            # Sync contact objects (requester and responder).
            # Check local cache first, to reduce the no. of API calls.
            if ft.requester_id:
                if FreshdeskContact.objects.filter(contact_id=ft.requester_id).exists():
                    ft.freshdesk_requester = FreshdeskContact.objects.get(contact_id=ft.requester_id)
                else:  # Attempt to cache the Freshdesk contact.
                    try:
                        data = get_freshdesk_object(obj_type='contacts', id=ft.requester_id)
                        contact = {}
                        contact['contact_id'] = data.pop('id')
                        contact['created_at'] = parse(data['created_at'])
                        contact['updated_at'] = parse(data['updated_at'])
                        # Pop any attributes from the dict which aren't in the FreshdeskContact model.
                        for d in data.keys():
                            if d in contact_keys:
                                contact[d] = data[d]
                        fdcon, create = FreshdeskContact.objects.update_or_create(**contact)
                        LOGGER.info('Created {}'.format(fdcon))
                        ft.freshdesk_requester = fdcon
                    except HTTPError:  # The GET might fail if the contact is an agent.
                        LOGGER.error('HTTP 404 Freshdesk contact not found: {}'.format(ft.requester_id))
                        pass
            if ft.responder_id:
                if FreshdeskContact.objects.filter(contact_id=ft.responder_id).exists():
                    ft.freshdesk_responder = FreshdeskContact.objects.get(contact_id=ft.responder_id)
                else:  # Attempt to cache the Freshdesk contact.
                    try:
                        data = get_freshdesk_object(obj_type='contacts', id=ft.responder_id)
                        contact = {}
                        contact['contact_id'] = data.pop('id')
                        contact['created_at'] = parse(data['created_at'])
                        contact['updated_at'] = parse(data['updated_at'])
                        # Pop any attributes from the dict which aren't in the FreshdeskContact model.
                        for d in data.keys():
                            if d in contact_keys:
                                contact[d] = data[d]
                        fdcon, create = FreshdeskContact.objects.update_or_create(**contact)
                        LOGGER.info('Created {}'.format(fdcon))
                        ft.freshdesk_responder = fdcon
                    except HTTPError:  # The GET might fail if the contact is an agent.
                        LOGGER.error('HTTP 404 Freshdesk contact not found: {}'.format(ft.responder_id))
                        pass
            ft.save()

            # Sync ticket conversation objects.
            obj = 'tickets/{}/conversations'.format(t['ticket_id'])
            convs = get_freshdesk_objects(obj_type=obj, progress=False, params={'page': 1})
            for c in convs:
                conv = {}
                # Rename key 'id'.
                conv['conversation_id'] = c.pop('id')
                # Date ISO8601-formatted date strings into datetimes.
                conv['created_at'] = parse(c['created_at'])
                conv['updated_at'] = parse(c['updated_at'])
                # Pop any attributes from the dict which aren't in the FreshdeskConversation model.
                for key in c.keys():
                    if key in conv_keys:
                        conv[key] = c[key]
                fc, create = FreshdeskConversation.objects.update_or_create(
                    conversation_id=conv['conversation_id'], defaults=conv)
                if create:
                    LOGGER.info('{} created'.format(fc))
                else:
                    LOGGER.info('{} updated'.format(fc))
                # Link parent ticket, DepartmentUser, etc.
                fc.freshdesk_ticket = ft
                if FreshdeskContact.objects.filter(contact_id=fc.user_id).exists():
                    fc.freshdesk_contact = FreshdeskContact.objects.get(contact_id=fc.user_id)
                else:  # Attempt to cache the Freshdesk contact.
                    try:
                        data = get_freshdesk_object(obj_type='contacts', id=fc.user_id)
                        contact = {}
                        contact['contact_id'] = data.pop('id')
                        contact['created_at'] = parse(data['created_at'])
                        contact['updated_at'] = parse(data['updated_at'])
                        # Pop any attributes from the dict which aren't in the FreshdeskContact model.
                        for d in data.keys():
                            if d in contact_keys:
                                contact[d] = data[d]
                        fdcon, create = FreshdeskContact.objects.update_or_create(**contact)
                        LOGGER.info('Created {}'.format(fdcon))
                        fc.freshdesk_contact = fdcon
                        # Attempt to match contact with a DepartmentUser.
                        fdcon.match_dept_user()
                    except HTTPError:  # The GET might fail if the contact is an agent.
                        LOGGER.error('HTTP 404 Freshdesk contact not found: {}'.format(ft.requester_id))
                        pass
                # Attempt to match conversation with a DepartmentUser.
                if fc.freshdesk_contact and DepartmentUser.objects.filter(email__iexact=fc.freshdesk_contact.email).exists():
                    fc.du_user = DepartmentUser.objects.get(email__iexact=fc.freshdesk_contact.email)
                fc.save()
        except Exception as e:
            LOGGER.exception(e)
            return False

    LOGGER.info('Ticket sync: {} created, {} updated'.format(created, updated))
    print('{} created, {} updated'.format(created, updated))

    return True
