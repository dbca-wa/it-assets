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


def scan(date):
    sweep = nmap.PortScanner()
    scans = []

    for scan_range in ScanRange.objects.filter(enabled=True):
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



def load_all():
    today = datetime.date.today()
    
    scan(today)
    HostStatus.objects.filter(date=today).update(
        monitor_status=1, monitor_url=None,
        vulnerability_status=1, vulnerability_url=None,
    )
    HostStatus.objects.filter(date=today, host__type=1).update(
        backup_status=0, backup_url=None,
        patching_status=0, patching_url=None,
    )
    HostStatus.objects.filter(date=today, host__type=0).update(
        backup_status=1, backup_url=None,
        patching_status=1, patching_url=None,
    )
    for plugin in ScanPlugin.objects.filter(enabled=True):
        plugin.run(today)
