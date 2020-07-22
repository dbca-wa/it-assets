import csv
from django.contrib.contenttypes.models import ContentType
from rancher.models import Workload
from registers.models import ITSystem
from nginx.models import SystemEnv, WebServer
from status.models import Host
from .models import Dependency, Platform, RiskAssessment


def load_platforms():
    f = open('platforms.csv', 'r')
    reader = csv.reader(f)
    next(reader)

    for row in reader:
        Platform.objects.create(name=row[0], health=row[1], tier=row[2])


def load_itsystem_platforms():
    f = open('systems_platforms.csv', 'r')
    reader = csv.reader(f)
    next(reader)

    for row in reader:
        it = ITSystem.objects.get(system_id=row[0])
        p = Platform.objects.get(name=row[1])
        it.platform = p
        it.save()


"""
Dependency graph update process:
    - Audit existing dependencies.
    - Generate / update WebServer deps ("Compute").
    - Generate / update WorkLoad deps ("Service").
    - Link WebServers to Hosts.
    - Create RiskAssessments from Host vuln scans (TODO: confirm business rule).
    - Create RiskAssessments for Workload image vuln scans (TODO: confirm business rule).
"""


def audit_dependencies():
    for dep in Dependency.objects.all():
        if not dep.content_object:  # Content object doesn't exist / invalid.
            dep.delete()


def create_webserver_dependencies():
    prod = SystemEnv.objects.get(name='prod')
    webserver_ct = ContentType.objects.get_for_model(WebServer.objects.first())

    for itsystem in ITSystem.objects.all():
        if itsystem.alias.exists():
            alias = itsystem.alias.first()  # Should only ever be one.
            webapps = alias.webapps.filter(redirect_to__isnull=True, system_env=prod)
            for webapp in webapps:
                locations = webapp.locations.all()
                for loc in locations:
                    loc_servers = loc.servers.all()
                    for loc_server in loc_servers:
                        webserver = loc_server.server
                        dep, created = Dependency.objects.get_or_create(
                            content_type=webserver_ct,
                            object_id=webserver.pk,
                            type='Compute',
                        )
                        itsystem.dependencies.add(dep)


def create_workload_dependencies():
    workload_ct = ContentType.objects.get_for_model(Workload.objects.first())

    for workload in Workload.objects.all().exclude(project__name='System'):
        for webapp in workload.webapps:
            if webapp.system_alias.system:
                dep, created = Dependency.objects.get_or_create(
                    content_type=workload_ct,
                    object_id=workload.pk,
                    category='Service',
                )
                webapp.system_alias.system.dependencies.add(dep)


def link_webservers_to_hosts():
    for i in WebServer.objects.all():
        if Host.objects.filter(name__istartswith=i.name):
            host = Host.objects.filter(name__istartswith=i.name).first()
            # print('{} -> {}'.format(i.name, host))
            i.host = host
            i.save()


def create_host_dependencies():
    # Follows creation of WebServer deps, and linking Webservers to Hosts.
    host_ct = ContentType.objects.get_for_model(Host.objects.first())
    webserver_ct = ContentType.objects.get_for_model(WebServer.objects.first())

    for i in WebServer.objects.filter(host__isnull=False):
        if Dependency.objects.filter(content_type=webserver_ct, object_id=i.pk).exists():
            webserver_dep = Dependency.objects.get(content_type=webserver_ct, object_id=i.pk)
            it_systems = ITSystem.objects.filter(dependencies__in=[webserver_dep])
            # Create a Host dependency
            host_dep, created = Dependency.objects.get_or_create(
                content_type=host_ct,
                object_id=i.host.pk,
                category='Compute',
            )
            # Add the Host dependency to IT Systems.
            for system in it_systems:
                system.dependencies.add(host_dep)


def set_host_risk_assessment_vulns():
    host_ct = ContentType.objects.get_for_model(Host.objects.first())

    for webserver in WebServer.objects.filter(host__isnull=False):
        status = webserver.host.statuses.latest()
        if status and status.vulnerability_info:
            # Our Host has been scanned by Nessus, so find that Host's matching Dependency
            # object, and create/update a RiskAssessment on it.
            if Dependency.objects.filter(content_type=host_ct, object_id=webserver.host.pk).exists():
                host_dep = Dependency.objects.get(content_type=host_ct, object_id=webserver.host.pk)
            else:
                host_dep = Dependency.objects.create(
                    content_type=host_ct,
                    object_id=webserver.host.pk,
                    category='Compute',
                )
            dep_ct = ContentType.objects.get_for_model(host_dep)
            if status.vulnerability_info['num_critical'] > 0:
                ra, created = RiskAssessment.objects.get_or_create(
                    content_type=dep_ct,
                    object_id=host_dep.pk,
                    category='Vulnerability',
                    rating=3,
                )
                ra.notes = 'Critical vulnerabilities present on host (Nessus).'
                ra.save()
            elif status.vulnerability_info['num_high'] > 0:
                ra, created = RiskAssessment.objects.get_or_create(
                    content_type=dep_ct,
                    object_id=host_dep.pk,
                    category='Vulnerability',
                    rating=2,
                )
                ra.notes = 'High vulnerabilities present on host (Nessus).'
                ra.save()
            elif status.vulnerability_info['num_medium'] > 0:
                ra, created = RiskAssessment.objects.get_or_create(
                    content_type=dep_ct,
                    object_id=host_dep.pk,
                    category='Vulnerability',
                    rating=1,
                )
                ra.notes = 'Low/medium vulnerabilities present on host (Nessus).'
                ra.save()
            else:
                ra, created = RiskAssessment.objects.get_or_create(
                    content_type=dep_ct,
                    object_id=host_dep.pk,
                    category='Vulnerability',
                    rating=0,
                )
                ra.notes = 'Vulnerabily scanning undertaken on host (Nessus).'
                ra.save()


def set_workload_risk_assessment_vulns():
    workload_ct = ContentType.objects.get_for_model(Workload.objects.first())
    dep_ct = ContentType.objects.get_for_model(Dependency.objects.first())

    for workload in Workload.objects.filter(image_scan_timestamp__isnull=False):
        if Dependency.objects.filter(content_type=workload_ct, object_id=workload.pk).exists():
            for dep in Dependency.objects.filter(content_type=workload_ct, object_id=workload.pk):
                vulns = workload.get_image_scan_vulns()
                if 'CRITICAL' in vulns:
                    ra, created = RiskAssessment.objects.get_or_create(
                        content_type=dep_ct,
                        object_id=dep.pk,
                        category='Vulnerability',
                        rating=3,
                    )
                    ra.notes = 'Workload image {} has {} critical vulns (trivy)'.format(workload.image, vulns['CRITICAL'])
                    ra.save()
                elif 'HIGH' in vulns:
                    ra, created = RiskAssessment.objects.get_or_create(
                        content_type=dep_ct,
                        object_id=dep.pk,
                        category='Vulnerability',
                        rating=2,
                    )
                    ra.notes = 'Workload image {} has {} high vulns (trivy)'.format(workload.image, vulns['HIGH'])
                    ra.save()
                elif 'MEDIUM' in vulns:
                    ra, created = RiskAssessment.objects.get_or_create(
                        content_type=dep_ct,
                        object_id=dep.pk,
                        category='Vulnerability',
                        rating=1,
                    )
                    ra.notes = 'Workload image {} has {} medium vulns (trivy)'.format(workload.image, vulns['MEDIUM'])
                    ra.save()
                else:
                    ra, created = RiskAssessment.objects.get_or_create(
                        content_type=dep_ct,
                        object_id=dep.pk,
                        category='Vulnerability',
                        rating=0,
                    )
                    ra.notes = 'Workload image {} has been scanned (trivy)'.format(workload.image)
                    ra.save()
