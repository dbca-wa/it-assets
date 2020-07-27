from django.contrib.contenttypes.models import ContentType
from rancher.models import Workload
from registers.models import ITSystem
from nginx.models import SystemEnv, WebServer
from status.models import Host
from .models import Dependency, RiskAssessment


def audit_dependencies():
    for dep in Dependency.objects.all():
        if not dep.content_object:  # Content object doesn't exist (usually an old/invalid PK).
            dep.delete()


def webserver_dependencies():
    # Create/update WebServer dependencies for IT systems as 'proxy targets'.
    # These are derived from Nginx proxy rule scans.
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
                            category='Proxy target',
                        )
                        itsystem.dependencies.add(dep)


def workload_dependencies():
    # Create/update k3s Workload dependencies for IT systems as 'services'.
    # These are derived from scans of Kubernetes clusters.
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


def host_dependencies():
    # Match webservers to hosts (based on name), and thereby set up host dependencies for
    # IT systems as 'compute' dependencies.
    host_ct = ContentType.objects.get_for_model(Host.objects.first())
    webserver_ct = ContentType.objects.get_for_model(WebServer.objects.first())

    # First, match webservers to hosts based on their name.
    for i in WebServer.objects.all():
        if Host.objects.filter(name__istartswith=i.name):
            host = Host.objects.filter(name__istartswith=i.name).first()
            i.host = host
            i.save()

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


def host_risk_assessment_vulns():
    # Set automatic risk assessment for Host objects that have a Nessus vulnerability scan result.
    host_ct = ContentType.objects.get_for_model(Host.objects.first())

    for host in Host.objects.all():
        status = host.statuses.latest()
        if status and status.vulnerability_info:
            # Our Host has been scanned by Nessus, so find that Host's matching Dependency
            # object, and create/update a RiskAssessment on it.
            if Dependency.objects.filter(content_type=host_ct, object_id=host.pk).exists():
                host_dep = Dependency.objects.get(content_type=host_ct, object_id=host.pk)
            else:
                host_dep = Dependency.objects.create(
                    content_type=host_ct,
                    object_id=host.pk,
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
                ra.notes = '[AUTOMATED ASSESSMENT] Critical vulnerabilities present on host (Nessus).'
                ra.save()
            elif status.vulnerability_info['num_high'] > 0:
                ra, created = RiskAssessment.objects.get_or_create(
                    content_type=dep_ct,
                    object_id=host_dep.pk,
                    category='Vulnerability',
                    rating=2,
                )
                ra.notes = '[AUTOMATED ASSESSMENT] High vulnerabilities present on host (Nessus).'
                ra.save()
            elif status.vulnerability_info['num_medium'] > 0:
                ra, created = RiskAssessment.objects.get_or_create(
                    content_type=dep_ct,
                    object_id=host_dep.pk,
                    category='Vulnerability',
                    rating=1,
                )
                ra.notes = '[AUTOMATED ASSESSMENT] Low/medium vulnerabilities present on host (Nessus).'
                ra.save()
            else:
                ra, created = RiskAssessment.objects.get_or_create(
                    content_type=dep_ct,
                    object_id=host_dep.pk,
                    category='Vulnerability',
                    rating=0,
                )
                ra.notes = '[AUTOMATED ASSESSMENT] Vulnerabily scanning undertaken on host (Nessus).'
                ra.save()


def workload_risk_assessment_vulns():
    # Set automatic risk assessment for Workload objects that have a trivy vulnerability scan.
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
                    ra.notes = '[AUTOMATED ASSESSMENT] Workload image {} has {} critical vulns (trivy)'.format(workload.image, vulns['CRITICAL'])
                    ra.save()
                elif 'HIGH' in vulns:
                    ra, created = RiskAssessment.objects.get_or_create(
                        content_type=dep_ct,
                        object_id=dep.pk,
                        category='Vulnerability',
                        rating=2,
                    )
                    ra.notes = '[AUTOMATED ASSESSMENT] Workload image {} has {} high vulns (trivy)'.format(workload.image, vulns['HIGH'])
                    ra.save()
                elif 'MEDIUM' in vulns:
                    ra, created = RiskAssessment.objects.get_or_create(
                        content_type=dep_ct,
                        object_id=dep.pk,
                        category='Vulnerability',
                        rating=1,
                    )
                    ra.notes = '[AUTOMATED ASSESSMENT] Workload image {} has {} medium vulns (trivy)'.format(workload.image, vulns['MEDIUM'])
                    ra.save()
                else:
                    ra, created = RiskAssessment.objects.get_or_create(
                        content_type=dep_ct,
                        object_id=dep.pk,
                        category='Vulnerability',
                        rating=0,
                    )
                    ra.notes = '[AUTOMATED ASSESSMENT] Workload image {} has been scanned (trivy)'.format(workload.image)
                    ra.save()


def itsystem_risks():
    # Set automatic risk assessment for IT system risk categories based on object field values.
    itsystem_ct = ContentType.objects.get_for_model(ITSystem.objects.first())

    for it in ITSystem.objects.all():
        if it.system_type:
            # Create/update a RiskAssessment object for the IT System.
            risk, created = RiskAssessment.objects.get_or_create(
                content_type=itsystem_ct,
                object_id=it.pk,
                category='Critical function',
                rating=2,
            )
            risk.notes = '[AUTOMATED ASSESSMENT] {}'.format(it.get_system_type_display())
            risk.save()

        if it.backups:
            risk, created = RiskAssessment.objects.get_or_create(
                content_type=itsystem_ct,
                object_id=it.pk,
                category='Backups',
                rating=it.backups - 1,
            )
            risk.notes = '[AUTOMATED ASSESSMENT] {}'.format(it.get_backups_display())
            risk.save()
