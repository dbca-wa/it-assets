from django.core.management.base import BaseCommand, CommandError
from bigpicture.utils import (
    audit_risks,
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
        self.stdout.write('Creating & updating system dependencies and risk assessments')
        self.stdout.write('Auditing existing risk and dependency objects')
        audit_risks()
        audit_dependencies()
        self.stdout.write('Creating/updating web server dependencies from Nginx proxy rules')
        webserver_dependencies()
        self.stdout.write('Creating/updating Kubernetes workload dependencies')
        workload_dependencies()
        self.stdout.write('Creating/updating host dependencies')
        host_dependencies()
        self.stdout.write('Creating/updating risk assessments for hosts')
        host_risk_assessment_vulns()
        self.stdout.write('Creating/updating risk assessments for k3s workloads')
        workload_risk_assessment_vulns()
        self.stdout.write('Creating/updating risk assessments for IT systems')
        itsystem_risks()
        self.stdout.write('Creating/updating risk assessments for host operating systems')
        host_os_risks()
        self.stdout.write('Complete')
