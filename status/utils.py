import multiprocessing
import socket
import datetime
import uuid

import logging
LOGGER = logging.getLogger('status_scans')

from django.conf import settings
import nmap
from django_q import tasks

from .models import Host, HostStatus, ScanRange, ScanPlugin, HostIP


def lookup_host(address):
    try:
        ip = socket.gethostbyname(address)
    except Exception:
        return None
    host_qs = Host.objects.filter(host_ips__ip=ip)
    if not host_qs:
        return None
    host = host_qs.first()
    return host


def lookup(address, date):
    host = lookup_host(address)
    if not host:
        return None
    host_status = HostStatus.objects.filter(host=host, date=date).first()
    return host_status


scan_write_lock = multiprocessing.Lock()
def scan_single(range_id, date=None):
    if date is None:
        date = datetime.date.today()
    scan_range = ScanRange.objects.get(id=range_id)
    LOGGER.info('Scanning {}...'.format(scan_range))
    
    sweep = nmap.PortScanner()
    for hosts in scan_range.range.split(','):
        sweep_data = sweep.scan(hosts=hosts, arguments='-sn -R --system-dns --host-timeout={}'.format(settings.STATUS_NMAP_TIMEOUT))['scan']

        scan_write_lock.acquire()
        try:
            for ipv4, context in sweep_data.items():
                host = lookup_host(ipv4)
                fqdn = context['hostnames'][0]['name'].lower() if context['hostnames'][0]['name'] else ipv4
                if host:
                    if host.name == ipv4 and host.name != fqdn and not Host.objects.filter(name=fqdn):
                        host.name = fqdn
                else:
                    host, _ = Host.objects.get_or_create(name=fqdn)
                host.save()
                if not host.active:
                    continue
                host_status, _ = HostStatus.objects.get_or_create(host=host, date=date)
                host_status.ping_status = 3
                host_status.ping_scan_range = scan_range
                host_status.save()
                host_ip = HostIP.objects.filter(ip=ipv4).first()
                if not host_ip:
                    host_ip = HostIP.objects.create(ip=ipv4, host=host)
                else:
                    host_ip.host = host
                host_ip.save()
        finally:
            scan_write_lock.release()

    LOGGER.info('Scan of {} complete.'.format(scan_range))



def scan(range_qs=None, date=None):
    if date is None:
        date = datetime.date.today()

    if range_qs is None:
        range_qs = ScanRange.objects.filter(enabled=True)

    group = 'status_scan_{}'.format(uuid.uuid4())

    count = 0
    for scan_range in range_qs:
        tasks.async_task('status.utils.scan_single', scan_range.id, date, group=group)
        count += 1
    results = tasks.result_group(group, failures=True, count=count)
    return results


def run_plugin(plugin_id):
    today = datetime.date.today()

    plugin = ScanPlugin.objects.filter(id=plugin_id).first()
    if plugin:
        plugin.run(today)


def run_scan(scan_id):
    today = datetime.date.today()
    scan_range = ScanRange.objects.filter(id=scan_id).first()
    HostStatus.objects.filter(date=today, ping_scan_range=scan_range).update(
        ping_status=0,
    )

    scan(ScanRange.objects.filter(id=scan_id), today)

    HostStatus.objects.filter(date=today, ping_scan_range=scan_range, ping_status=0).update(
        ping_status=1,
    )



def run_all():
    today = datetime.date.today()

    # full scan, so create blanks for any hosts in the host list
    for host in Host.objects.filter(active=True):
        host_status, _ = HostStatus.objects.get_or_create(date=today, host=host)
    
    # pre-emptively zero out results for today
    HostStatus.objects.filter(date=today).update(
        ping_status=0,
        monitor_status=0, monitor_plugin=None, monitor_output='', monitor_url=None,
        vulnerability_status=0, vulnerability_plugin=None, vulnerability_output='', vulnerability_url=None,
        backup_status=0, backup_plugin=None, backup_output='', backup_url=None,
        patching_status=0, patching_plugin=None, patching_output='', patching_url=None,
    )

    # ping scan all the enabled ranges
    try:
        LOGGER.info('Running a full scan')
        scan(ScanRange.objects.filter(enabled=True), today)
    except Exception as e:
        LOGGER.error('Failed to complete scan')
        LOGGER.exception(e)
    
    # flag any remaining hosts as missing ping
    HostStatus.objects.filter(date=today, ping_status=0).update(ping_status=1)

    # run all the enabled plugins
    for plugin in ScanPlugin.objects.filter(enabled=True):
        try:
            LOGGER.info('Running plugin {}'.format(plugin.name))
            plugin.run(today)
        except Exception as e:
            LOGGER.error('Failed to run plugin {}'.format(plugin.name))
            LOGGER.exception(e)

    # for everything, flag missing monitoring and vulnerability
    HostStatus.objects.filter(date=today, monitor_status=0).update(monitor_status=1)
    HostStatus.objects.filter(date=today, vulnerability_status=0).update(vulnerability_status=1)

    # for servers only, flag missing backup and patching
    HostStatus.objects.filter(date=today, host__type=0, backup_status=0).update(backup_status=1)
    HostStatus.objects.filter(date=today, host__type=0, patching_status=0).update(patching_status=1)
