from datetime import timedelta
from django.contrib.contenttypes.models import ContentType
from rancher.models import Workload
from registers.models import ITSystem
from nginx.models import SystemEnv, WebServer, WebAppAccessDailyReport
from status.models import Host
from statistics import mean, stdev, StatisticsError
from .models import Dependency, RiskAssessment


def audit_risks():
    for risk in RiskAssessment.objects.all():
        if not risk.content_object:  # Content object doesn't exist (usually an old/invalid PK).
            risk.delete()


def audit_dependencies():
    for dep in Dependency.objects.all():
        if not dep.content_object:  # Content object doesn't exist (usually an old/invalid PK).
            dep.delete()


def webserver_dependencies():
    # Create/update WebServer dependencies for IT systems as 'proxy targets'.
    # These are derived from Nginx proxy rule scans.
    prod = SystemEnv.objects.get(name='prod')
    webserver_ct = ContentType.objects.get_for_model(WebServer.objects.first())

    for it in ITSystem.objects.all():
        # Remove any existing webserver dependencies.
        for dep in it.dependencies.filter(content_type=webserver_ct):
            it.dependencies.remove(dep)
        # Link current webserver dependencies.
        if it.alias.exists():
            for alias in it.alias.all():
                alias = it.alias.first()
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
                            it.dependencies.add(dep)


def workload_dependencies():
    # Create/update k3s Workload dependencies for IT systems as 'services'.
    # These are derived from scans of Kubernetes clusters.
    workload_ct = ContentType.objects.get_for_model(Workload.objects.first())

    # Remove any existing IT System workload dependencies.
    for it in ITSystem.objects.all():
        for dep in it.dependencies.filter(content_type=workload_ct):
            it.dependencies.remove(dep)

    # Link current workload dependencies.
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

    # First, try to match webservers to hosts based on their name.
    for i in WebServer.objects.filter(host__isnull=True):
        if Host.objects.filter(name__istartswith=i.name).exists():
            host = Host.objects.filter(name__istartswith=i.name).first()
            i.host = host
            i.save()
        elif i.other_names:  # Fall back to trying the other names for the Webserver (if applicable).
            for name in i.other_names:
                if Host.objects.filter(name__istartswith=name).exists():
                    host = Host.objects.filter(name__istartswith=name).first()
                    i.host = host
                    i.save()

    for i in WebServer.objects.filter(host__isnull=False):
        if Dependency.objects.filter(content_type=webserver_ct, object_id=i.pk, category='Proxy target').exists():
            webserver_dep = Dependency.objects.get(content_type=webserver_ct, object_id=i.pk, category='Proxy target')
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


def host_risks_vulns():
    # Set automatic risk assessment for Host objects that have a Nessus vulnerability scan result.
    host_ct = ContentType.objects.get_for_model(Host.objects.first())

    for host in Host.objects.all():
        if host.statuses.exists():
            status = host.statuses.latest()
        else:
            status = None
        if status and status.vulnerability_info:
            # Our Host has been scanned by Nessus, so find that Host's matching Dependency
            # object, and create/update a RiskAssessment on it.
            # TODO: delete this risk if applicable.
            host_dep, created = Dependency.objects.get_or_create(
                content_type=host_ct,
                object_id=host.pk,
                category='Compute'
            )
            dep_ct = ContentType.objects.get_for_model(host_dep)

            if RiskAssessment.objects.filter(content_type=dep_ct, object_id=host_dep.pk, category='Vulnerability').exists():
                ra = RiskAssessment.objects.get(content_type=dep_ct, object_id=host_dep.pk, category='Vulnerability')
            else:
                ra = RiskAssessment(content_type=dep_ct, object_id=host_dep.pk, category='Vulnerability')

            if status.vulnerability_info['num_critical'] > 0:
                ra.rating = 3
                ra.notes = '[AUTOMATED ASSESSMENT] Critical vulnerabilities present on host (Nessus).'
            elif status.vulnerability_info['num_high'] > 0:
                ra.rating = 2
                ra.notes = '[AUTOMATED ASSESSMENT] High vulnerabilities present on host (Nessus).'
            elif status.vulnerability_info['num_medium'] > 0:
                ra.rating = 1
                ra.notes = '[AUTOMATED ASSESSMENT] Low/medium vulnerabilities present on host (Nessus).'
            else:
                ra.rating = 0
                ra.notes = '[AUTOMATED ASSESSMENT] Vulnerabily scanning undertaken on host (Nessus).'
            ra.save()


# List of EoL OS name fragments, as output by Nessus.
OS_EOL = [
    'Microsoft Windows 7',
    'Microsoft Windows Server 2003',
    'Microsoft Windows Server 2008',
    'Microsoft Windows Server 2012',
    'Ubuntu 14.04',
]


def host_os_risks():
    # Set auto risk assessment for Host risk based on the host OS.
    host_ct = ContentType.objects.get_for_model(Host.objects.first())

    for host in Host.objects.all():
        if host.statuses.exists():
            status = host.statuses.latest()
            if 'os' in status.vulnerability_info and status.vulnerability_info['os']:
                host_dep, created = Dependency.objects.get_or_create(
                    content_type=host_ct,
                    object_id=host.pk,
                    category='Compute'
                )
                dep_ct = ContentType.objects.get_for_model(host_dep)
                risky_os = None

                for os in OS_EOL:
                    if os in status.vulnerability_info['os']:
                        risky_os = status.vulnerability_info['os']
                        break

                # NOTE: we can't use get_or_create here, because we may need to update the rating
                # value of a RiskAssessment, and the field is non-nullable.
                if RiskAssessment.objects.filter(content_type=dep_ct, object_id=host_dep.pk, category='Operating System').exists():
                    risk = RiskAssessment.objects.get(content_type=dep_ct, object_id=host_dep.pk, category='Operating System')
                else:
                    risk = RiskAssessment(
                        content_type=dep_ct,
                        object_id=host_dep.pk,
                        category='Operating System',
                        rating=0,
                    )
                if risky_os:
                    risk.notes = '[AUTOMATED ASSESSMENT] Host operating system ({}) is past end-of-life'.format(risky_os)
                    risk.rating = 3
                else:
                    risk.notes = '[AUTOMATED ASSESSMENT] Host operating system ({}) supported'.format(status.vulnerability_info['os'])
                    risk.rating = 0
                risk.save()


def workload_risks_vulns():
    # Set automatic risk assessment for Workload objects that have a trivy vulnerability scan.
    workload_ct = ContentType.objects.get_for_model(Workload.objects.first())
    dep_ct = ContentType.objects.get_for_model(Dependency.objects.first())

    for workload in Workload.objects.filter(image_scan_timestamp__isnull=False):
        if Dependency.objects.filter(content_type=workload_ct, object_id=workload.pk).exists():
            for dep in Dependency.objects.filter(content_type=workload_ct, object_id=workload.pk):
                # Vulnerabilities
                vulns = workload.get_image_scan_vulns()

                if RiskAssessment.objects.filter(content_type=dep_ct, object_id=dep.pk, category='Vulnerability').exists():
                    ra = RiskAssessment.objects.get(content_type=dep_ct, object_id=dep.pk, category='Vulnerability')
                else:
                    ra = RiskAssessment(content_type=dep_ct, object_id=dep.pk, category='Vulnerability')

                if 'CRITICAL' in vulns:
                    ra.rating = 3
                    ra.notes = '[AUTOMATED ASSESSMENT] Workload image {} has {} critical vulnerabilities (trivy)'.format(workload.image, vulns['CRITICAL'])
                elif 'HIGH' in vulns:
                    ra.rating = 2
                    ra.notes = '[AUTOMATED ASSESSMENT] Workload image {} has {} high vulnerabilities (trivy)'.format(workload.image, vulns['HIGH'])
                elif 'MEDIUM' in vulns:
                    ra.rating = 1
                    ra.notes = '[AUTOMATED ASSESSMENT] Workload image {} has {} medium vulnerabilities (trivy)'.format(workload.image, vulns['MEDIUM'])
                else:
                    ra.rating = 0
                    ra.notes = '[AUTOMATED ASSESSMENT] Workload image {} has been scanned (trivy)'.format(workload.image)
                ra.save()

                # Operating System
                os = workload.get_image_scan_os()
                if os:
                    if RiskAssessment.objects.filter(content_type=dep_ct, object_id=dep.pk, category='Operating System').exists():
                        risk = RiskAssessment.objects.get(content_type=dep_ct, object_id=dep.pk, category='Operating System')
                    else:
                        risk = RiskAssessment(content_type=dep_ct, object_id=dep.pk, category='Operating System')
                    if os in OS_EOL:
                        risk.notes = '[AUTOMATED ASSESSMENT] Workload image operating system ({}) is past end-of-life'.format(os)
                        risk.rating = 3
                    else:
                        risk.notes = '[AUTOMATED ASSESSMENT] Workload image operating system ({}) supported'.format(os)
                        risk.rating = 0
                    risk.save()


def itsystem_risks_critical_function(it_systems=None):
    """Set automatic risk assessment for IT systems based on whether they are noted as used for a critical function.
    """
    if not it_systems:
        it_systems = ITSystem.objects.all()
    itsystem_ct = ContentType.objects.get_for_model(it_systems.first())

    for it in it_systems:
        # First, check if an auto assessment has been created OR if not assessment exists.
        # If so, carry on. If not, skip automated assessment (assumes that a manual assessment exists,
        # which we don't want to overwrite).
        if (
            RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Critical function', notes__contains='[AUTOMATED ASSESSMENT]').exists()
            or not RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Critical function').exists()
        ):
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
            else:
                # If system_type is not recorded for the IT system but there is a risk of this type, delete the risk.
                risk = RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Critical function').first()
                if risk:
                    risk.delete()


def itsystem_risks_backups(it_systems=None):
    """Set automatic risk assessment for IT systems based on whether they have a backup method recorded.
    """
    if not it_systems:
        it_systems = ITSystem.objects.all()
    itsystem_ct = ContentType.objects.get_for_model(it_systems.first())

    for it in it_systems:
        # First, check if an auto assessment has been created OR if not assessment exists.
        # If so, carry on. If not, skip automated assessment (assumes that a manual assessment exists,
        # which we don't want to overwrite).
        if (
            RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Backups', notes__contains='[AUTOMATED ASSESSMENT]').exists()
            or not RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Backups').exists()
        ):
            backup_risk = RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Backups').first()
            if it.backups:
                if not backup_risk:
                    backup_risk = RiskAssessment(content_type=itsystem_ct, object_id=it.pk, category='Backups')
                if it.backups == 1:  # Daily local with point in time DB recovery.
                    backup_risk.rating = 0
                else:
                    backup_risk.rating = 1  # Daily local / vendor-managed.
                backup_risk.notes = '[AUTOMATED ASSESSMENT] {}'.format(it.get_backups_display())
            else:
                if not backup_risk:
                    backup_risk = RiskAssessment(content_type=itsystem_ct, object_id=it.pk, category='Backups')
                backup_risk.rating = 2
                backup_risk.notes = '[AUTOMATED ASSESSMENT] No backup scheme is recorded'
            backup_risk.save()


def itsystem_risks_support(it_systems=None):
    """Set automatic risk assessment for IT systems based on whether they have a BH support contact.
    """
    if not it_systems:
        it_systems = ITSystem.objects.all()
    itsystem_ct = ContentType.objects.get_for_model(it_systems.first())

    for it in it_systems:
        # First, check if an auto assessment has been created OR if not assessment exists.
        # If so, carry on. If not, skip automated assessment (assumes that a manual assessment exists,
        # which we don't want to overwrite).
        if (
            RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Support', notes__contains='[AUTOMATED ASSESSMENT]').exists()
            or not RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Support').exists()
        ):
            support_risk = RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Support').first()
            if not it.bh_support:
                if not support_risk:
                    support_risk = RiskAssessment(content_type=itsystem_ct, object_id=it.pk, category='Support')
                support_risk.rating = 2
                support_risk.notes = '[AUTOMATED ASSESSMENT] No business hours support contact is recorded'
            else:
                if not support_risk:
                    support_risk = RiskAssessment(content_type=itsystem_ct, object_id=it.pk, category='Support')
                support_risk.rating = 0
                support_risk.notes = '[AUTOMATED ASSESSMENT] Business hours support contact is recorded'
            support_risk.save()


def itsystem_risks_access(it_systems=None):
    """Set automatic risk assessment for IT system web apps based on whether they require SSO on the root location.
    """
    if not it_systems:
        it_systems = ITSystem.objects.all()
    itsystem_ct = ContentType.objects.get_for_model(it_systems.first())
    prod = SystemEnv.objects.get(name='prod')

    for it in it_systems:
        if it.alias.exists():
            # First, check if an auto assessment has been created OR if not assessment exists.
            # If so, carry on. If not, skip automated assessment (assumes that a manual assessment exists,
            # which we don't want to overwrite).
            if (
                RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Access', notes__contains='[AUTOMATED ASSESSMENT]').exists()
                or not RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Access').exists()
            ):
                for alias in it.alias.all():
                    webapps = alias.webapps.filter(redirect_to__isnull=True, system_env=prod)
                    for webapp in webapps:
                        root_location = webapp.locations.filter(location='/').first()
                        if root_location:
                            # Create an access risk
                            risk = RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Access').first()
                            if not risk:
                                risk = RiskAssessment(content_type=itsystem_ct, object_id=it.pk, category='Access')
                            if root_location.auth_type == 0:
                                if webapp.clientip_subnet:
                                    risk.rating = 1
                                    risk.notes = '[AUTOMATED ASSESSMENT] Web application root location does not require SSO, but is restricted to internal subnets'
                                else:
                                    risk.rating = 2
                                    risk.notes = '[AUTOMATED ASSESSMENT] Web application root location does not require SSO and is not restricted to internal subnets'
                            else:
                                risk.rating = 0
                                risk.notes = '[AUTOMATED ASSESSMENT] Web application root location requires SSO'
                            risk.save()
                        else:
                            # If any access risk exists, delete it.
                            if RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Access').exists():
                                risk = RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Access').first()
                                risk.delete()


def itsystem_risks_traffic(it_systems=None):
    """Set automatic risk assessment for IT system web apps based on the mean of daily HTTP requests.
    """
    if not it_systems:
        it_systems = ITSystem.objects.all()
    itsystem_ct = ContentType.objects.get_for_model(it_systems.first())
    prod = SystemEnv.objects.get(name='prod')

    for it in it_systems:
        # First, check if an auto assessment has been created OR if not assessment exists.
        # If so, carry on. If not, skip automated assessment (assumes that a manual assessment exists,
        # which we don't want to overwrite).
        if (
            RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Traffic', notes__contains='[AUTOMATED ASSESSMENT]').exists()
            or not RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Traffic').exists()
        ):
            if it.alias.exists():
                requests = []
                for alias in it.alias.all():
                    webapps = alias.webapps.filter(redirect_to__isnull=True, system_env=prod)
                    for webapp in webapps:
                        if not webapp.dailyreports.exists():
                            continue
                        report = webapp.dailyreports.latest()
                        # Statistics mangling alert: due to the number of requests being 'bursty', we take
                        # the daily count of requests for the last 28 days, calculate the Z-score for each,
                        # discard any that are greater than 2 or less than -2, then calculate the mean of
                        # the remaining values.
                        # This is completely arbitrary and subject to change.
                        last_log_day = report.log_day
                        start_date = (last_log_day - timedelta(days=27))
                        reports = WebAppAccessDailyReport.objects.filter(webapp=webapp, log_day__gte=start_date)
                        for i in reports:
                            requests.append(i.requests)
                if requests:
                    try:
                        μ = mean(requests)
                        σ = stdev(requests)
                        if σ:  # Avoid a ZeroDivisionError.
                            requests_filter = []
                            for i in requests:
                                if -2.0 <= ((i - μ) / σ) <= 2.0:
                                    requests_filter.append(i)
                            requests_mean = int(mean(requests_filter))
                        else:
                            requests_mean = int(mean(requests))
                    except StatisticsError:
                        requests_mean = int(mean(requests))

                    risk = RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Traffic').first()
                    if not risk:
                        risk = RiskAssessment(content_type=itsystem_ct, object_id=it.pk, category='Traffic')
                    if requests_mean >= 10000:
                        risk.rating = 3
                        risk.notes = '[AUTOMATED ASSESSMENT] High traffic of daily HTTP requests'
                    elif requests_mean >= 1000:
                        risk.rating = 2
                        risk.notes = '[AUTOMATED ASSESSMENT] Moderate traffic of daily HTTP requests'
                    elif requests_mean >= 100:
                        risk.rating = 1
                        risk.notes = '[AUTOMATED ASSESSMENT] Low traffic of daily HTTP requests'
                    else:
                        risk.rating = 0
                        risk.notes = '[AUTOMATED ASSESSMENT] Minimal traffic of daily HTTP requests'
                    risk.save()
