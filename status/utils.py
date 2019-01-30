import nmap
import adal
import requests

import socket
import urllib
import csv
import datetime

from django.conf import settings

from .models import Host, HostStatus, ScanRange, HostIP


def lookup(address, date):
    try:
        ip = socket.gethostbyname(address)
    except Exception:
        return None
    host_qs = Host.objects.filter(host_ips__ip=ip)
    if not host_qs:
        return None
    host = host_qs.first()
    host_status = HostStatus.objects.filter(host=host, date=date).first()
    return host_status


def scan():
    sweep = nmap.PortScanner()
    scans = []

    for scan_range in ScanRange.objects.filter(enabled=True):
        print('Scanning {}...'.format(scan_range))
        for hosts in scan_range.range.split(','):
            scans.append((scan_range, sweep.scan(hosts=hosts, arguments='-sn -R --system-dns')['scan']))
    
    today = datetime.date.today()

    HostStatus.objects.filter(date=today).update(ping_status=1)

    for scan_range, sweep_data in scans:
        for ipv4, context in sweep_data.items():
            fqdn = context['hostnames'][0]['name'].lower() if context['hostnames'][0]['name'] else ipv4
            host, _ = Host.objects.get_or_create(name=fqdn)
            host.save()
            host_status, _ = HostStatus.objects.get_or_create(host=host, date=today)
            host_status.ping_status = 3
            host_status.ping_scan_range = scan_range
            host_status.save()
            host_ip = HostIP.objects.filter(ip=ipv4).first()
            if not host_ip:
                host_ip = HostIP.objects.create(ip=ipv4, host=host)
            else:
                host_ip.host = host
            host_ip.save()


def load_monitor():
    print('Loading device monitoring...')
    PRTG_DEVICES = '{}/api/table.json?content=devices&output=json&columns=objid,host,probe,device,active&count=2000&username={}&passhash={}'.format(settings.PRTG_BASE, settings.PRTG_USERNAME, settings.PRTG_PASSHASH)
    report = requests.get(PRTG_DEVICES, verify=False).json()

    today = datetime.date.today()
    HostStatus.objects.filter(date=today).update(monitor_status=1, monitor_url=None)

    for device in report['devices']:
        host_status = lookup(device['host'], today)
        if host_status is None:
            continue
        
        host_status.monitor_info = {
            'id': device['objid'],
            'device_name': device['device'],
            'probe': device['probe'],
            'active': device['active']
        }
        host_status.monitor_status = 3 if device['active'] else 2
        host_status.monitor_url = '{}/device.htm?id={}'.format(settings.PRTG_URL, device['objid'])
        host_status.save()


def load_vulnerability():
    print('Loading vulnerability reports...')
    NESSUS_HEADERS = {'X-ApiKeys': 'accessKey={}; secretKey={}'.format(settings.NESSUS_ACCESS_KEY, settings.NESSUS_SECRET_KEY), 'Content-Type': 'application/json', 'Accept': 'text/plain'}
    NESSUS_SCAN_FOLDER = 3
    NESSUS_SCANS = '{}/scans?folder_id={}'.format(settings.NESSUS_BASE, settings.NESSUS_SCAN_FOLDER)
    NESSUS_REPORT = lambda x: '{}/scans/{}'.format(settings.NESSUS_BASE, x)

    reports = requests.get(NESSUS_SCANS, headers=NESSUS_HEADERS, verify=False).json()

    today = datetime.date.today()
    HostStatus.objects.filter(date=today).update(vulnerability_status=1, vulnerability_url=None)

    for report in reports['scans']:
        data = requests.get(NESSUS_REPORT(report['id']), headers=NESSUS_HEADERS, verify=False).json()
        if data['info']['policy'].startswith('Web'):
            continue
        name = data['info']['name']

        print('Report {} ({})'.format(name, report['id']))
        for report_host in data['hosts']:
            #print('{}: {} {} {} {} {} - {} {}'.format(host['hostname'], host['critical'], host['high'], host['medium'], host['low'], host['info'], host['severity'], host['score']))
            
            host_status = lookup(report_host['hostname'], today)
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
            host_status.vulnerability_status = 3 if (int(report_host['critical']) == 0) and (int(report_host['high']) == 0) else 2
            host_status.vulnerability_url = '{}/#/scans/reports/{}/hosts/{}/vulnerabilities'.format(settings.NESSUS_URL, report['id'], report_host['host_id'])
            host_status.save()


def load_patching():
    LOG_ANALYTICS_BASE = 'https://api.loganalytics.io'
    LOG_ANALYTICS_QUERY = '{}/v1/workspaces/{}/query'.format(LOG_ANALYTICS_BASE, settings.AZURE_LOG_WORKSPACE)
    ctx = adal.AuthenticationContext(settings.AZURE_TENANT)
    token = ctx.acquire_token_with_client_credentials(LOG_ANALYTICS_BASE, settings.AZURE_APP_ID, settings.AZURE_APP_KEY)
    patching = requests.get(LOG_ANALYTICS_QUERY, params={
        'query': "(ConfigurationData | project Computer, TimeGenerated, VMUUID | distinct Computer) | join kind=inner ( Heartbeat | project Computer, OSType, OSName, OSMajorVersion, OSMinorVersion, ComputerEnvironment, TimeGenerated, TenantId, ComputerIP | summarize arg_max (TimeGenerated, *) by Computer ) on Computer"
    }, headers={'Authorization': 'Bearer {}'.format(token['accessToken'])})
    results = patching.json()

    today = datetime.date.today()
    HostStatus.objects.filter(date=today, host__type=0).update(patching_status=1)
    
    for computer in results['tables'][0]['rows']:
        host_status = lookup(computer[0], today)
        if host_status is None:
            continue
        host_status.patching_info = {
            'id': computer[8],
            'os_type': computer[3],
            'os_name': computer[4],
            'os_major_version': computer[5],
            'os_minor_version': computer[6],
        }
        host_status.patching_status = 3
        host_status.save()


def load_backup():
    print('Loading backup list...')
    ACRONIS_AUTH = '{}/idp/authorize/local/'.format(settings.ACRONIS_BASE)
    ACRONIS_RESOURCES = '{}/api/ams/resources_v2?filter=all&limit=2000'.format(settings.ACRONIS_BASE)

    sess = requests.session()
    base = sess.get(settings.ACRONIS_BASE)
    req_qs = urllib.parse.urlparse(base.url).query
    req_id = urllib.parse.parse_qs(req_qs)['req'][0]
    auth = sess.post(ACRONIS_AUTH+'?{}'.format(req_qs), {'req': req_id, 'login': settings.ACRONIS_USERNAME, 'password': settings.ACRONIS_PASSWORD})
    resources = sess.get(ACRONIS_RESOURCES).json()

    today = datetime.date.today()    
    HostStatus.objects.filter(date=today, host__type=0).update(backup_status=1)

    for agent in resources['data']:
        host_status = None
        if 'ip' not in agent:
            continue
        for ip in agent['ip']:
            host_status = lookup(ip, today)
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
        host_status.backup_status = 3 if agent.get('status') == 'ok' else 2
        host_status.save()



def load_all():
    scan()
    load_monitor()
    load_vulnerability()
    load_patching()
    load_backup()
