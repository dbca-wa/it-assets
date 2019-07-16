import datetime
import re
import urllib

import adal
import boto3
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

    requests.packages.urllib3.disable_warnings()

    reports = requests.get(NESSUS_SCANS, headers=NESSUS_HEADERS, verify=False).json()

    for report in reports['scans']:
        data = requests.get(NESSUS_REPORT(report['id']), headers=NESSUS_HEADERS, verify=False).json()
        if data['info']['policy'].startswith('Web'):
            continue
        name = data['info']['name']

        #print('Report {} ({})'.format(name, report['id']))
        for report_host in data['hosts']:
            #print('{}: {} {} {} {} {} - {} {}'.format(host['hostname'], host['critical'], host['high'], host['medium'], host['low'], host['info'], host['severity'], host['score']))
            
            host_status = lookup(report_host['hostname'], date)
            if host_status is None:
                continue
            os = None
            detail = requests.get(NESSUS_VULNS(report['id'], report_host['host_id']), headers=NESSUS_HEADERS, verify=False).json()
            if 'operating-system' in detail['info']:
                os = detail['info']['operating-system']
            #print((report_host['hostname'], os))
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
                'os': os
            }
            host_status.vulnerability_plugin = plugin
            host_status.vulnerability_output = 'Device has been scanned, vulnerabilities were found'
            host_status.vulnerability_status = 2


            if (int(report_host['critical']) == 0) and (int(report_host['high']) == 0):
                name_check = [x['plugin_name'] for x in detail['vulnerabilities']]
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

    ACRONIS_AUTH = '{}/idp/authorize/local'.format(ACRONIS_BASE)
    ACRONIS_RESOURCES = '{}/api/resource_manager/v1/resources?filter=all&limit=2000&embed=details&embed=agent'.format(ACRONIS_BASE)

    backup_limit = (datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()


    sess = requests.session()
    base = sess.get(ACRONIS_BASE)
    req_qs = urllib.parse.urlparse(base.url).query
    #req_id = urllib.parse.parse_qs(req_qs)['req'][0]

    req_id = re.search('/idp/authorize/sspi\?req=([a-z0-9]+)', base.content.decode('utf8')).group(1)

    auth = sess.post(ACRONIS_AUTH+'?req_id={}'.format(req_id), {'req': req_id, 'login': ACRONIS_USERNAME, 'password': ACRONIS_PASSWORD})
    resources = sess.get(ACRONIS_RESOURCES).json()

    for agent in resources['items']:
        host_status = None
        if 'details' not in agent or 'parameters' not in agent['details']:
            continue
        if 'IP' not in agent['details']['parameters']:
            continue
        for ip in agent['details']['parameters']['IP']:
            host_status = lookup(ip, date)
            if host_status:
                break
        if 'status' not in agent:
            continue
        if not host_status or agent['status'].get('lastBackup') is None:
            continue

        os_name = None
        if 'OperatingSystem' in agent['details']['parameters']:
            os_name = agent['details']['parameters']['OperatingSystem'][0]
        next_backup = None
        if 'nextBackup' in agent['status'] and agent['status']['nextBackup'] is not None:
            next_backup = datetime.datetime.fromisoformat(agent['status']['nextBackup'].split('Z', 1)[0])
        last_backup = None
        if 'lastBackup' in agent['status'] and agent['status']['lastBackup'] is not None:
            last_backup = datetime.datetime.fromisoformat(agent['status']['lastBackup'].split('Z', 1)[0])

        state = agent['status'].get('state')

        if 'last_backup' in host_status.backup_info and last_backup < datetime.datetime.fromisoformat(host_status.backup_info['last_backup']):
            continue
        host_status.backup_info = {
            'id': agent.get('id'),
            'next_backup': next_backup.isoformat() if next_backup else None,
            'last_backup': last_backup.isoformat() if last_backup else None,
            'os': os_name,
            'status': state,
        }
        host_status.backup_url = '{}/#m=Resources&key=All devices'.format(ACRONIS_URL, )
        host_status.backup_plugin = plugin
        if state == 'notProtected' and last_backup is not None:
            host_status.backup_output = 'Device is present, automatic backups are disabled'
            host_status.backup_status = 2
        elif not (host_status.backup_info['last_backup'] is not None and host_status.backup_info['last_backup'] > backup_limit): 
            host_status.backup_output = 'Device is present, last backup older than 24 hours.'
            host_status.backup_status = 2
        else:
            host_status.backup_output = 'Device is present, last backup was successful.'
            host_status.backup_status = 3
         
        host_status.save()


def backup_aws(plugin, date):
    AWS_ACCESS_KEY_ID = plugin.params.get(name='AWS_ACCESS_KEY_ID').value
    AWS_SECRET_ACCESS_KEY = plugin.params.get(name='AWS_SECRET_ACCESS_KEY').value
    AWS_REGION = plugin.params.get(name='AWS_REGION').value
    AWS_URL = 'https://{0}.console.aws.amazon.com/ec2/v2/home?region={0}#Instances:search='.format(AWS_REGION)

    client = boto3.client('ec2', 
        aws_access_key_id=AWS_ACCESS_KEY_ID, 
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )

    snapshot_limit = (datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()

    instance_map = {}
    volume_map = {}
    # scrape information from EC2 instances list
    instances = client.describe_instances()
    for resv in instances['Reservations']:
        for inst in resv['Instances']:
            key = inst['InstanceId']
            instance_map[key] = {
                'id': key,
                'ips': [x['PrivateIpAddress'] for x in inst['NetworkInterfaces']],
                'volumes': [],
                'snapshots': {},
            }
            # find name
            for tag in inst['Tags']:
                if tag['Key'].lower() == 'name':
                    instance_map[key]['name'] = tag['Value']
                    break
            # find all volumes
            for volume in inst['BlockDeviceMappings']:
                if 'Ebs' in volume:
                    instance_map[key]['volumes'].append(volume['Ebs']['VolumeId'])
                    volume_map[volume['Ebs']['VolumeId']] = key

    # scrape information from snapshots list
    snapshots = client.describe_snapshots()
    for snap in snapshots['Snapshots']:
        if snap['State'] != 'completed':
            continue
        volume = snap['VolumeId']
        if not volume in volume_map:
            continue
        key = volume_map[volume]
        if not volume in instance_map[key]['snapshots']:
            instance_map[key]['snapshots'][volume] = []
        instance_map[key]['snapshots'][volume].append(snap['StartTime'])

    for instance in instance_map.values():
        for ip in instance['ips']:
            host_status = lookup(ip, date)
            if host_status:
                break
        if not host_status:
            continue
        host_status.backup_plugin = plugin
        host_status.backup_url = AWS_URL+instance['id']
        host_status.backup_info = {
            'id': instance['id'],
            'name': instance['name'],
            'volumes': []
        }
        for v in instance['volumes']:
            snaps = sorted(instance['snapshots'].get(v, []), reverse=True)
            last_backup = snaps[0].isoformat() if snaps else None
            host_status.backup_info['volumes'].append({
                'id': v,
                'snap_count': len(snaps),
                'last_backup': last_backup,
            })
        
        if not all([v['snap_count'] for v in host_status.backup_info['volumes']]):
            host_status.backup_output = 'A volume has not been snapshotted.'
            host_status.backup_status = 2
        elif not all ([(v['last_backup'] is not None and v['last_backup'] > snapshot_limit) for v in host_status.backup_info['volumes']]):
            host_status.backup_output = 'A volume does not have a snapshot from the last 24 hours.'
            host_status.backup_status = 2
        else:
            host_status.backup_output = 'Daily snapshotting was successful.'
            host_status.backup_status = 3
        host_status.save()


def _ms_api(verb, url, previous=None, **kwargs):
    req = requests.request(verb, url, **kwargs)
    data = req.json()
    
    result = []
    if previous is not None:
        result = previous

    if 'value' not in data:
        return result
    result.extend(data['value'])
    if '@nextLink' in data:
        return _ms_api(verb, data['@nextLink'], previous=result, **kwargs)
    return result


def backup_azure(plugin, date):
    AZURE_TENANT = plugin.params.get(name='AZURE_TENANT').value
    AZURE_APP_ID = plugin.params.get(name='AZURE_APP_ID').value
    AZURE_APP_KEY = plugin.params.get(name='AZURE_APP_KEY').value
    AZURE_SUBSCRIPTION_ID = plugin.params.get(name='AZURE_SUBSCRIPTION_ID').value
    AZURE_VAULT_NAME = plugin.params.get(name='AZURE_VAULT_NAME').value

    AZURE_URL = 'https://portal.azure.com/#resource{}/backupSetting'

    MANAGEMENT_BASE = 'https://management.azure.com'
    MANAGEMENT_SUB = '{}/subscriptions/{}'.format(MANAGEMENT_BASE, AZURE_SUBSCRIPTION_ID)

    ctx = adal.AuthenticationContext(AZURE_TENANT)
    token = ctx.acquire_token_with_client_credentials(MANAGEMENT_BASE, AZURE_APP_ID, AZURE_APP_KEY)
    headers = {'Authorization': 'Bearer {}'.format(token['accessToken'])}

    MANAGEMENT_LIST_VMS = '{}/providers/Microsoft.Compute/virtualMachines?api-version=2018-06-01'.format(MANAGEMENT_SUB)
    vms = _ms_api('GET', MANAGEMENT_LIST_VMS, headers=headers)

    # Get the ID of the specified vault.
    MANAGEMENT_LIST_VAULTS = '{}/providers/Microsoft.RecoveryServices/vaults?api-version=2016-06-01'.format(MANAGEMENT_SUB)
    vaults = _ms_api('GET', MANAGEMENT_LIST_VAULTS, headers=headers)

    vault = None
    for v in vaults:
        if v['name'] == AZURE_VAULT_NAME:
            vault = v['id']
            break
    if vault is None:
        return

    # Get backup protection container list.
    MANAGEMENT_LIST_CONTAINERS = '{}{}/backupProtectionContainers?api-version=2016-12-01&$filter=backupManagementType%20eq%20%27AzureIaasVM%27%20and%20status%20eq%20%27Registered%27'.format(MANAGEMENT_BASE, vault)
    containers = _ms_api('GET', MANAGEMENT_LIST_CONTAINERS, headers=headers)

    vm_mapping = {}
    for container in containers:
        vm_id = container['properties']['virtualMachineId']
        if vm_id not in vm_mapping:
            vm_mapping[vm_id] = {}
        vm_mapping[vm_id]['id'] = vm_id
        vm_mapping[vm_id]['container_name'] = container['name']
        vm_mapping[vm_id]['container_id'] = container['id']
        vm_mapping[vm_id]['container_health'] = container['properties']['healthStatus']
        vm_mapping[vm_id]['ips'] = []

    # Get private IP addresses of each VM
    MANAGEMENT_LIST_NICS = '{}/providers/Microsoft.Network/networkInterfaces?api-version=2018-10-01'.format(MANAGEMENT_SUB)
    nics = _ms_api('GET', MANAGEMENT_LIST_NICS, headers=headers)

    for nic in nics:
        if 'virtualMachine' not in nic['properties']:
            continue
        vm_id = nic['properties']['virtualMachine']['id']
        if vm_id in vm_mapping:
            vm_mapping[vm_id]['ips'] = [x['properties']['privateIPAddress'] for x in nic['properties']['ipConfigurations']]

    for vm in vm_mapping.values():
        host_status = None
        for ip in vm['ips']:
            host_status = lookup(ip, date)
            if host_status:
                break
        if not host_status:
            continue
        host_status.backup_plugin = plugin
        host_status.backup_url = AZURE_URL.format(vm['id'])
        host_status.backup_info = {
            'id': vm['id'],
            'container_name': vm['container_name'],
            'container_id': vm['container_id'],
            'container_health': vm['container_health'],
        }
        if vm['container_health'] == 'Healthy':
            host_status.backup_output = 'VM is enrolled for backups and is healthy.'
            host_status.backup_status = 3
        else:
            host_status.backup_output = 'VM is enrolled for backups, but is not healthy.'
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
    headers = {'Authorization': 'Bearer {}'.format(token['accessToken'])}
    patching = requests.get(LOG_ANALYTICS_QUERY, params={
        'query': "(ConfigurationData | project Computer, TimeGenerated, VMUUID | distinct Computer) | join kind=inner ( Heartbeat | project Computer, OSType, OSName, OSMajorVersion, OSMinorVersion, ComputerEnvironment, TimeGenerated, TenantId, ComputerIP | summarize arg_max (TimeGenerated, *) by Computer ) on Computer"
    }, headers=headers)
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


