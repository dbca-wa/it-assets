from django.core.management.base import BaseCommand, CommandError
import traceback
from bigpicture.utils import (
    audit_dependencies,
    webserver_dependencies,
    workload_dependencies,
    host_dependencies,
    host_risk_assessment_vulns,
    workload_risk_assessment_vulns,
    itsystem_risks,
    host_os_risks,
)


"""
Dependency graph update process:
    - Audit existing dependencies.
    - Generate / update WebServer deps ("Proxy target").
    - Generate / update WorkLoad deps ("Service").
    - Link WebServers to Hosts.
    - Generate / update Host deps ("Compute").
    - Create RiskAssessments from Host vuln scans (TODO: confirm business rule).
    - Create RiskAssessments for Workload image vuln scans (TODO: confirm business rule).
"""


class Command(BaseCommand):
    help = 'Creates & updates dependencies and risk assessments from scan data'

    def handle(self, *args, **options):
        try:
            print('Creating & updating system dependencies and risk assessments')
            print('Auditing existing dependency objects')
            audit_dependencies()
            print('Creating/updating web server dependencies from Nginx proxy rules')
            webserver_dependencies()
            print('Creating/updating Kubernetes workload dependencies')
            workload_dependencies()
            print('Creating/updating host dependencies')
            host_dependencies()
            print('Creating/updating risk assessments for hosts')
            host_risk_assessment_vulns()
            print('Creating/updating risk assessments for k3s workloads')
            workload_risk_assessment_vulns()
            print('Creating/updating risk assessments for IT systems')
            itsystem_risks()
            print('Creating/updating risk assessments for host operating systems')
            host_os_risks()
            print('Complete')
        except:
            raise CommandError('Error during generation of dependencies & risk assessments')
            traceback.print_exception()
