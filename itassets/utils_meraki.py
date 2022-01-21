from django.conf import settings
import requests
from itassets.utils import human_time_duration


MERAKI_AUTH_HEADERS = {
    'X-Cisco-Meraki-API-Key': settings.MERAKI_API_KEY,
    'Content-Type': 'application/json',
}


def get_meraki_orgs():
    url = 'https://api.meraki.com/api/v1/organizations'
    resp = requests.get(url, headers=MERAKI_AUTH_HEADERS)
    resp.raise_for_status()
    return resp.json()


def get_meraki_networks(org_id):
    url = f'https://api.meraki.com/api/v1/organizations/{org_id}/networks'
    resp = requests.get(url, headers=MERAKI_AUTH_HEADERS)
    resp.raise_for_status()
    networks = resp.json()

    while 'next' in resp.links:
        url = resp.links['next']['url']
        resp = requests.get(url, headers=MERAKI_AUTH_HEADERS)
        resp.raise_for_status()
        networks = networks + resp.json()

    return resp.json()


def get_meraki_clients(network_id, timespan=1209600):
    """timespan is in seconds, default value is 14 days.
    """
    url = f'https://api.meraki.com/api/v1/networks/{network_id}/clients?timespan={timespan}'
    resp = requests.get(url, headers=MERAKI_AUTH_HEADERS)
    resp.raise_for_status()
    clients = resp.json()

    while 'next' in resp.links:
        url = resp.links['next']['url']
        resp = requests.get(url, headers=MERAKI_AUTH_HEADERS)
        resp.raise_for_status()
        clients = clients + resp.json()

    return resp.json()


def get_client_desc_html(client, network, timespan):
    duration = human_time_duration(timespan)
    return f"Asset <a href='{network['url']}/overview#c={client['id']}'>{client['description']} ({client['ip']})</a> was last seen on VLAN {client['vlan']} in the network <a href='{network['url']}'>{network['name']}</a> and has used {client['usage']['total']} KB data in the past {duration}."
