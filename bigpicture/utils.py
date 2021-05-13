import calendar
import csv
from data_storage import AzureBlobStorage
from datetime import timedelta
from dbca_utils.utils import env
from django.contrib.contenttypes.models import ContentType
import gzip
import json
import requests
from urllib.parse import urlparse

from rancher.models import Workload
from registers.models import ITSystem
from status.models import Host
from .models import Dependency, RiskAssessment


def audit_risks():
    for risk in RiskAssessment.objects.all():
        if not risk.content_object:  # Content object doesn't exist (usually an old/invalid PK).
            risk.delete()


def audit_dependencies():
    for dep in Dependency.objects.all():
        if not dep.content_object:  # Content object doesn't exist (usually an old/invalid PK).
            dep.delete()


def host_dependencies():
    # Download the list of Nginx host proxy targets.
    connect_string = env('AZURE_CONNECTION_STRING')
    store = AzureBlobStorage(connect_string, 'analytics')
    store.download('nginx_host_proxy_targets.json', 'nginx_host_proxy_targets.json')
    f = open('nginx_host_proxy_targets.json')
    targets = json.loads(f.read())
    host_ct = ContentType.objects.get(app_label='status', model='host')

    # Production / Production (legacy) systems only.
    for it in ITSystem.objects.filter(link__isnull=False, status__in=[0, 2]).exclude(link=''):
        # Remove any existing IT System Host dependencies.
        for dep in it.dependencies.filter(content_type=host_ct):
            it.dependencies.remove(dep)

        if 'url_synonyms' not in it.extra_data or not it.extra_data['url_synonyms']:
            # Skip this IT System (no known URL or synonyms).
            continue

    # Create/update Host dependencies for IT systems as 'proxy targets'.
    target = None
    for syn in it.extra_data['url_synonyms']:
        for t in targets:
            if syn == t['host']:
                target = t
                break
        if target:
            for p in target["proxy_pass"]:
                u = urlparse(p)
                host = u.netloc.split(':')[0]
                if Host.objects.filter(name=host).exists():
                    h = Host.objects.filter(name=host).first()
                    host_dep, created = Dependency.objects.get_or_create(
                        content_type=host_ct,
                        object_id=h.pk,
                        category='Proxy target',
                    )
                    # Add the dependency to the IT System.
                    it.dependencies.add(host_dep)


def workload_dependencies():
    # Create/update k3s Workload dependencies for IT systems as 'services'.
    # These are derived from scans of Kubernetes clusters.
    workload_ct = ContentType.objects.get(app_label='rancher', model='workload')

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


def host_risks_vulns():
    # Set automatic risk assessment for Host objects that have a Nessus vulnerability scan result.
    host_ct = ContentType.objects.get(app_label='status', model='host')

    for host in Host.objects.all():
        if host.statuses.exists():
            status = host.statuses.latest()
        else:
            status = None
        if status and status.vulnerability_info:
            # Our Host has been scanned by Nessus, so find that Host's matching Dependency
            # object, and create/update a RiskAssessment on it.
            host_dep, created = Dependency.objects.get_or_create(
                content_type=host_ct,
                object_id=host.pk,
                category='Proxy target'
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
    host_ct = ContentType.objects.get(app_label='status', model='host')

    for host in Host.objects.all():
        if host.statuses.exists():
            status = host.statuses.latest()
            if 'os' in status.vulnerability_info and status.vulnerability_info['os']:
                host_dep, created = Dependency.objects.get_or_create(
                    content_type=host_ct,
                    object_id=host.pk,
                    category='Proxy target'
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
    workload_ct = ContentType.objects.get(app_label='rancher', model='workload')
    dep_ct = ContentType.objects.get(app_label='bigpicture', model='dependency')

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


def itsystem_risks_infra_location(it_systems=None):
    """Set automatic risk assessment for IT systems based on whether they have an infrastructure location recorded.
    """
    if not it_systems:
        it_systems = ITSystem.objects.all()
    itsystem_ct = ContentType.objects.get(app_label='registers', model='itsystem')

    for it in it_systems:
        # First, check if an auto assessment has been created OR if no assessment exists.
        # If so, carry on. If not, skip automated assessment (assumes that a manual assessment exists,
        # which we don't want to overwrite).
        if (
            RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Infrastructure location', notes__contains='[AUTOMATED ASSESSMENT]').exists()
            or not RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Infrastructure location').exists()
        ):
            location_risk = RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Infrastructure location').first()
            if it.infrastructure_location:
                if not location_risk:
                    location_risk = RiskAssessment(content_type=itsystem_ct, object_id=it.pk, category='Infrastructure location')
                if it.infrastructure_location in [2, 3, 4]:  # Azure / AWS / other provider cloud.
                    location_risk.rating = 0
                elif it.infrastructure_location == 1:  # On-premises.
                    location_risk.rating = 3
                location_risk.notes = '[AUTOMATED ASSESSMENT] {}'.format(it.get_infrastructure_location_display())
                location_risk.save()
            else:
                # If infrastructure_location is not recorded for the IT system but there is a risk of this type, delete the risk.
                location_risk = RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Infrastructure location').first()
                if location_risk:
                    location_risk.delete()


def itsystem_risks_critical_function(it_systems=None):
    """Set automatic risk assessment for IT systems based on whether they are noted as used for a critical function.
    """
    if not it_systems:
        it_systems = ITSystem.objects.all()
    itsystem_ct = ContentType.objects.get(app_label='registers', model='itsystem')

    for it in it_systems:
        # First, check if an auto assessment has been created OR if no assessment exists.
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
    itsystem_ct = ContentType.objects.get(app_label='registers', model='itsystem')

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
    itsystem_ct = ContentType.objects.get(app_label='registers', model='itsystem')

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

    # Download the list of Nginx host proxy targets.
    connect_string = env('AZURE_CONNECTION_STRING')
    store = AzureBlobStorage(connect_string, 'analytics')
    store.download('nginx_host_proxy_targets.json', 'nginx_host_proxy_targets.json')
    f = open('nginx_host_proxy_targets.json')
    targets = json.loads(f.read())
    itsystem_ct = ContentType.objects.get(app_label='registers', model='itsystem')

    for it in it_systems:
        # First, check if an auto assessment has been created OR if no assessment exists.
        # If so, carry on. If not, skip automated assessment (assumes that a manual assessment exists,
        # which we don't want to overwrite).
        if (
            RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Access', notes__contains='[AUTOMATED ASSESSMENT]').exists()
            or not RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Access').exists()
        ):
            if 'url_synonyms' not in it.extra_data or not it.extra_data['url_synonyms']:
                # Skip this IT System (no known URL or synonyms).
                continue

            target = None

            # Get/create an access risk
            risk = RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Access').first()
            if not risk:
                risk = RiskAssessment(content_type=itsystem_ct, object_id=it.pk, category='Access')

            for syn in it.extra_data['url_synonyms']:
                for t in targets:
                    if syn == t['host']:
                        target = t
                        break
                if target:
                    if 'sso_locations' in target:
                        if '/' in target['sso_locations'] or '^~ /' in target['sso_locations'] or '= /' in target['sso_locations']:
                            risk.rating = 0
                            risk.notes = '[AUTOMATED ASSESSMENT] Web application root location requires SSO'
                        else:
                            risk.rating = 1
                            risk.notes = '[AUTOMATED ASSESSMENT] Web application locations configured to require SSO'
                    else:
                        if 'custom/dpaw_subnets' in target['includes']:
                            risk.rating = 1
                            risk.notes = '[AUTOMATED ASSESSMENT] Web application root location does not require SSO, but is restricted to internal subnets'
                        else:
                            risk.rating = 2
                            risk.notes = '[AUTOMATED ASSESSMENT] Web application root location does not require SSO and is not restricted to internal subnets'
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
    # Download the report of HTTP requests.
    connect_string = env('AZURE_CONNECTION_STRING')
    store = AzureBlobStorage(connect_string, 'analytics')
    store.download('host_requests_7_day_count.csv', 'host_requests_7_day_count.csv')
    counts = csv.reader(open('host_requests_7_day_count.csv'))
    next(counts)  # Skip the header.
    report = {}
    for row in counts:
        try:
            report[row[0]] = int(row[1])
        except:
            # Sometimes the report contains junk rows; just ignore these.
            pass
    itsystem_ct = ContentType.objects.get(app_label='registers', model='itsystem')

    for it in it_systems:
        # First, check if an auto assessment has been created OR if not assessment exists.
        # If so, carry on. If not, skip automated assessment (assumes that a manual assessment exists,
        # which we don't want to overwrite).
        if (
            RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Traffic', notes__contains='[AUTOMATED ASSESSMENT]').exists()
            or not RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Traffic').exists()
        ):
            if 'url_synonyms' not in it.extra_data or not it.extra_data['url_synonyms']:
                # Skip this IT System (no known URL or synonyms).
                continue

            # Get/create a Traffic risk
            risk = RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Traffic').first()
            if not risk:
                risk = RiskAssessment(content_type=itsystem_ct, object_id=it.pk, category='Traffic')

            for syn in it.extra_data['url_synonyms']:
                if syn in report and report[syn] >= 100:
                    requests_mean = report[syn] / 7
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
                else:  # Volume of HTTP traffic is too small to assess.
                    # If any Traffic risk exists, delete it.
                    if RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Traffic').exists():
                        risk = RiskAssessment.objects.filter(content_type=itsystem_ct, object_id=it.pk, category='Traffic').first()
                        risk.delete()


def signal_sciences_extract_feed(from_datetime=None, minutes=None):
    """Extract the Signal Sciences feed for ``minutes`` duration from the passed-in timestamp (UTC).
    Returns the feed JSON as a string.
    """
    if not from_datetime or not minutes:
        return False
    ss_email = env('SIGSCI_EMAIL', None)
    api_token = env('SIGSCI_API_TOKEN', None)
    if not ss_email and not api_token:
        return False

    api_host = env('SIGSCI_API_HOST', 'https://dashboard.signalsciences.net')
    corp_name = env('SIGSCI_CORP_NAME', 'dbca')
    site_name = env('SIGSCI_SITE_NAME', 'www.dbca.wa.gov.au')
    from_datetime = from_datetime.replace(second=0, microsecond=0)  # Ensure lowest precision is minutes.
    from_time = calendar.timegm(from_datetime.utctimetuple())
    until_datetime = from_datetime + timedelta(minutes=minutes)
    until_time = calendar.timegm(until_datetime.utctimetuple())
    headers = {
        'x-api-user': ss_email,
        'x-api-token': api_token,
        'Content-Type': 'application/json',
    }
    url = api_host + '/api/v0/corps/{}/sites/{}/feed/requests?from={}&until={}'.format(corp_name, site_name, from_time, until_time)
    first = True
    feed_str = '['

    while True:
        resp_raw = requests.get(url, headers=headers)
        response = json.loads(resp_raw.text)
        for request in response['data']:
            data = json.dumps(request)
            if first:
                first = False
            else:
                data = ',' + data
            feed_str += (data)
        next_url = response['next']['uri']
        if next_url == '':
            feed_str += ']'
            break
        url = api_host + next_url

    return feed_str


def signal_sciences_upload_feed(from_datetime=None, minutes=None, compress=False, upload=True, csv=False):
    """For the given datetime and duration, download the Signal Sciences feed and upload the data
    to Azure blob storage (optionally compress the file using gzip).
    Optionally also upload a CSV summary of tagged requests to blob storage.
    """
    if not from_datetime or not minutes:
        return False
    feed_str = signal_sciences_extract_feed(from_datetime, minutes)
    corp_name = env('SIGSCI_CORP_NAME', 'dbca')

    if upload and csv:
        signal_sciences_feed_csv(feed_str, corp_name, from_datetime.isoformat())

    if compress:
        # Conditionally gzip the file.
        filename = 'sigsci_feed_{}_{}.json.gz'.format(corp_name, from_datetime.strftime('%Y-%m-%dT%H%M%S'))
        tf = gzip.open('/tmp/{}'.format(filename), 'wb')
        tf.write(feed_str.encode('utf-8'))
    else:
        filename = 'sigsci_feed_{}_{}.json'.format(corp_name, from_datetime.strftime('%Y-%m-%dT%H%M%S'))
        tf = open('/tmp/{}'.format(filename), 'w')
        tf.write(feed_str)
    tf.close()

    if upload:
        # Upload the returned feed data to blob storage.
        connect_string = env('AZURE_CONNECTION_STRING')
        store = AzureBlobStorage(connect_string, 'signalsciences')
        store.upload_file(filename, tf.name)

    return filename


def signal_sciences_feed_csv(feed_str, corp_name, timestamp, upload=True):
    """For a given passed-in Signal Sciences feed string, summarise it to a CSV for analysis.
    Upload the CSV to Azure blob storage.
    """
    filename = 'sigsci_request_tags_{}_{}.csv'.format(corp_name, timestamp)
    tf = open('/tmp/{}'.format(filename), 'w')
    writer = csv.writer(tf)
    feed_json = json.loads(feed_str)

    for entry in feed_json:
        for tag in entry['tags']:
            writer.writerow([entry['timestamp'], entry['serverName'], tag['type']])

    tf.close()

    if upload:
        connect_string = env('AZURE_CONNECTION_STRING')
        store = AzureBlobStorage(connect_string, 'http-requests-tagged')
        store.upload_file(filename, tf.name)

    return
