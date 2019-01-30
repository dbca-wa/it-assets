import nmap

import socket
import datetime

from django.conf import settings

from .models import Host, HostStatus, ScanRange, ScanPlugin, HostIP


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


def scan(range_qs=None, date=None):
    sweep = nmap.PortScanner()
    scans = []

    if date is None:
        date = datetime.date.today()

    if range_qs is None:
        range_qs = ScanRange.objects.filter(enabled=True)

    for scan_range in range_qs:
        print('Scanning {}...'.format(scan_range))
        for hosts in scan_range.range.split(','):
            scans.append((scan_range, sweep.scan(hosts=hosts, arguments='-sn -R --system-dns')['scan']))
    
    HostStatus.objects.filter(date=date).update(ping_status=1)

    for scan_range, sweep_data in scans:
        for ipv4, context in sweep_data.items():
            fqdn = context['hostnames'][0]['name'].lower() if context['hostnames'][0]['name'] else ipv4
            host, _ = Host.objects.get_or_create(name=fqdn)
            host.save()
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


def run_plugin(plugin_id):
    today = datetime.date.today()

    plugin = ScanPlugin.objects.filter(id=plugin_id).first()
    if plugin:
        plugin.run(today)


def run_scan(scan_id):
    today = datetime.date.today()
    
    scan(ScanRange.objects.filter(id=scan_id), today)


def run_all():
    today = datetime.date.today()

    # pre-emptively zero out results for today
    HostStatus.objects.filter(date=today).update(
        monitor_status=0, monitor_url=None,
        vulnerability_status=0, vulnerability_url=None,
        backup_status=0, backup_url=None,
        patching_status=0, patching_url=None,
    )

    # ping scan all the enabled ranges
    scan(today)

    # run all the enabled plugins
    for plugin in ScanPlugin.objects.filter(enabled=True):
        plugin.run(today)

    # for everything, flag missing monitoring and vulnerability
    HostStatus.objects.filter(date=today, monitor_status=0).update(monitor_status=1)
    HostStatus.objects.filter(date=today, vulnerability_status=0).update(vulnerability_status=1)

    # for servers only, flag missing backup and patching
    HostStatus.objects.filter(date=today, host__type=0, backup_status=0).update(backup_status=1)
    HostStatus.objects.filter(date=today, host__type=0, patching_status=0).update(patching_status=1)
