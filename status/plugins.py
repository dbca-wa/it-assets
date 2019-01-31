import datetime
import urllib

import adal
import requests

from .models import Host, HostStatus, ScanRange, ScanPlugin, HostIP
from .utils import lookup


def monitor_prtg(plugin, date):
    PRTG_BASE = plugin.params.get(name='PRTG_BASE').value
    PRTG_USERNAME = plugin.params.get(name='PRTG_USERNAME').value
    PRTG_PASSHASH = plugin.params.get(name='PRTG_PASSHASH').value
    PRTG_URL = plugin.params.get(name='PRTG_URL').value
    
    PRTG_DEVICES = '{}/api/table.json?content=devices&output=json&columns=objid,host,probe,device,active,status,upsens&count=2000&username={}&passhash={}'.format(PRTG_BASE, PRTG_USERNAME, PRTG_PASSHASH)
    report = requests.get(PRTG_DEVICES, verify=False).json()

    for device in report['devices']:
        host_status = lookup(device['host'], date)
        if host_status is None:
            continue
        
        host_status.monitor_info = {
            'id': device['objid'],
            'device_name': device['device'],
            'probe': device['probe'],
            'active': device['active'],
            'status': device['status'],
            'sensors_up': device['upsens_raw'],
        }
        host_status.monitor_plugin = plugin
        if device['active'] and device['upsens_raw']:
            host_status.monitor_status = 3
            host_status.monitor_output = 'Device is monitored.'
        elif device['active'] and not device['upsens_raw']:
            host_status.monitor_status = 2
            host_status.monitor_output = 'Device is monitored, but no sensors are up.'
        else:
            host_status.monitor_status = 2
            host_status.monitor_output = 'Device has been added to monitoring, but is deactivated.'

        host_status.monitor_url = '{}/device.htm?id={}'.format(PRTG_URL, device['objid'])
        host_status.save()


def vulnerability_nessus(plugin, date):
    NESSUS_BASE = plugin.params.get(name='NESSUS_BASE').value
    NESSUS_ACCESS_KEY = plugin.params.get(name='NESSUS_ACCESS_KEY').value
    NESSUS_SECRET_KEY = plugin.params.get(name='NESSUS_SECRET_KEY').value
    NESSUS_SCAN_FOLDER = plugin.params.get(name='NESSUS_SCAN_FOLDER').value
    NESSUS_URL = plugin.params.get(name='NESSUS_URL').value

    NESSUS_HEADERS = {'X-ApiKeys': 'accessKey={}; secretKey={}'.format(NESSUS_ACCESS_KEY, NESSUS_SECRET_KEY), 'Content-Type': 'application/json', 'Accept': 'text/plain'}
    NESSUS_SCAN_FOLDER = 3
    NESSUS_SCANS = '{}/scans?folder_id={}'.format(NESSUS_BASE, NESSUS_SCAN_FOLDER)
    NESSUS_REPORT = lambda scan_id: '{}/scans/{}'.format(NESSUS_BASE, scan_id)
    NESSUS_VULNS = lambda scan_id, host_id: '{}/scans/{}/hosts/{}'.format(NESSUS_BASE, scan_id, host_id)

    reports = requests.get(NESSUS_SCANS, headers=NESSUS_HEADERS, verify=False).json()

    for report in reports['scans']:
        data = requests.get(NESSUS_REPORT(report['id']), headers=NESSUS_HEADERS, verify=False).json()
        if data['info']['policy'].startswith('Web'):
            continue
        name = data['info']['name']

        print('Report {} ({})'.format(name, report['id']))
        for report_host in data['hosts']:
            #print('{}: {} {} {} {} {} - {} {}'.format(host['hostname'], host['critical'], host['high'], host['medium'], host['low'], host['info'], host['severity'], host['score']))
            
            host_status = lookup(report_host['hostname'], date)
            if host_status is None:
                continue
            host_status.vulnerability_info = {
                'id': report_host['host_id'],
                'report_id': report['id'],
                'scan_name': data['info']['name'],
                'scan_start': datetime.datetime.fromtimestamp(data['info']['scan_start'], datetime.timezone.utc).isoformat(),
                'scan_end': datetime.datetime.fromtimestamp(data['info']['scan_end'], datetime.timezone.utc).isoformat(),
                'severity': report_host['severity'],
                'score': report_host['score'],
                'num_critical': report_host['critical'],
                'num_high': report_host['high'],
                'num_medium': report_host['medium'],
                'num_low': report_host['low'],
                'num_info': report_host['info'],
            }
            host_status.vulnerability_plugin = plugin
            host_status.vulnerability_output = 'Device has been scanned, vulnerabilities were found'
            host_status.vulnerability_status = 2
            if (int(report_host['critical']) == 0) and (int(report_host['high']) == 0):
                vulns = requests.get(NESSUS_VULNS(report['id'], report_host['host_id']), headers=NESSUS_HEADERS, verify=False).json()
                name_check = [x['plugin_name'] for x in vulns['vulnerabilities']]
                if 'Authentication Failure - Local Checks Not Run' in name_check:
                    host_status.vulnerability_output = 'Device is being scanned, but does not have correct credentials.'
                else:
                    host_status.vulnerability_output = 'Device has been scanned, no critical or high vulnerabilities were found.'
                    host_status.vulnerability_status = 3
            host_status.vulnerability_url = '{}/#/scans/reports/{}/hosts/{}/vulnerabilities'.format(NESSUS_URL, report['id'], report_host['host_id'])
            host_status.save()


def backup_acronis(plugin, date):
    ACRONIS_BASE = plugin.params.get(name='ACRONIS_BASE').value
    ACRONIS_USERNAME = plugin.params.get(name='ACRONIS_USERNAME').value
    ACRONIS_PASSWORD = plugin.params.get(name='ACRONIS_PASSWORD').value
    ACRONIS_URL = plugin.params.get(name='ACRONIS_URL').value

    ACRONIS_AUTH = '{}/idp/authorize/local/'.format(ACRONIS_BASE)
    ACRONIS_RESOURCES = '{}/api/ams/resources_v2?filter=all&limit=2000'.format(ACRONIS_BASE)

    sess = requests.session()
    base = sess.get(ACRONIS_BASE)
    req_qs = urllib.parse.urlparse(base.url).query
    req_id = urllib.parse.parse_qs(req_qs)['req'][0]
    auth = sess.post(ACRONIS_AUTH+'?{}'.format(req_qs), {'req': req_id, 'login': ACRONIS_USERNAME, 'password': ACRONIS_PASSWORD})
    resources = sess.get(ACRONIS_RESOURCES).json()

    for agent in resources['data']:
        host_status = None
        if 'ip' not in agent:
            continue
        for ip in agent['ip']:
            host_status = lookup(ip, date)
            if host_status:
                break
        if not host_status or agent.get('lastBackup') is None:
            continue
        next_backup = datetime.datetime.fromisoformat(agent['nextBackup']) if 'nextBackup' in agent and agent['nextBackup'] is not None else None
        last_backup = datetime.datetime.fromisoformat(agent['lastBackup']) if 'lastBackup' in agent and agent['lastBackup'] is not None else None

        if 'last_backup' in host_status.backup_info and last_backup < datetime.datetime.fromisoformat(host_status.backup_info['last_backup']):
            continue
        host_status.backup_info = {
            'id': agent.get('id'),
            'next_backup': next_backup.isoformat() if next_backup else None,
            'last_backup': last_backup.isoformat() if last_backup else None,
            'os': agent.get('os'),
            'status': agent.get('status'),
        }
        host_status.backup_plugin = plugin
        if agent.get('status') == 'ok':
            host_status.backup_output = 'Device is present, last backup was successful.'
            host_status.backup_status = 3
        else: 
            host_status.backup_output = 'Device is present, last backup failed.'
            host_status.backup_status = 2
        host_status.save()


def patching_oms(plugin, date):
    AZURE_TENANT = plugin.params.get(name='AZURE_TENANT').value
    AZURE_APP_ID = plugin.params.get(name='AZURE_APP_ID').value
    AZURE_APP_KEY = plugin.params.get(name='AZURE_APP_KEY').value
    AZURE_LOG_WORKSPACE = plugin.params.get(name='AZURE_LOG_WORKSPACE').value
    
    LOG_ANALYTICS_BASE = 'https://api.loganalytics.io'
    LOG_ANALYTICS_QUERY = '{}/v1/workspaces/{}/query'.format(LOG_ANALYTICS_BASE, AZURE_LOG_WORKSPACE)
    ctx = adal.AuthenticationContext(AZURE_TENANT)
    token = ctx.acquire_token_with_client_credentials(LOG_ANALYTICS_BASE, AZURE_APP_ID, AZURE_APP_KEY)
    patching = requests.get(LOG_ANALYTICS_QUERY, params={
        'query': "(ConfigurationData | project Computer, TimeGenerated, VMUUID | distinct Computer) | join kind=inner ( Heartbeat | project Computer, OSType, OSName, OSMajorVersion, OSMinorVersion, ComputerEnvironment, TimeGenerated, TenantId, ComputerIP | summarize arg_max (TimeGenerated, *) by Computer ) on Computer"
    }, headers={'Authorization': 'Bearer {}'.format(token['accessToken'])})
    results = patching.json()

    for computer in results['tables'][0]['rows']:
        host_status = lookup(computer[0], date)
        if host_status is None:
            continue
        host_status.patching_info = {
            'id': computer[8],
            'os_type': computer[3],
            'os_name': computer[4],
            'os_major_version': computer[5],
            'os_minor_version': computer[6],
        }
        host_status.patching_plugin = plugin
        host_status.patching_output = 'Server has been enrolled in OMS.'
        host_status.patching_status = 3
        host_status.save()


