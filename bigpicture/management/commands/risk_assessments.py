from django.core.management.base import BaseCommand
import logging
from bigpicture import utils
from registers.models import ITSystem


"""
Dependency graph update process:
    - Audit existing dependencies.
    - Generate / update WebServer deps ("Proxy target").
    - Generate / update WorkLoad deps ("Service").
    - Link WebServers to Hosts.
    - Generate / update Host deps ("Compute").
    - Create RiskAssessments from Host vuln scans (TODO: confirm business rule).
    - Create RiskAssessments for Workload image vuln scans (TODO: confirm business rule).
    - Create RiskAssessments for IT systems.
"""


class Command(BaseCommand):
    help = 'Creates & updates dependencies and risk assessments from scan data'

    def add_arguments(self, parser):
        parser.add_argument('--active', action='store_false', help='Only audit active/prod services')

    def handle(self, *args, **options):
        logger = logging.getLogger('bigpicture')
        logger.info('Creating & updating system dependencies and risk assessments')
        logger.info('Auditing existing risk and dependency objects')
        utils.audit_risks()
        utils.audit_dependencies()
        logger.info('Creating/updating Kubernetes workload dependencies')
        utils.workload_dependencies()
        logger.info('Creating/updating host dependencies')
        utils.host_dependencies()
        logger.info('Creating/updating risk assessments for host operating systems')
        utils.host_os_risks()
        logger.info('Creating/updating risk assessments for hosts')
        utils.host_risks_vulns()
        logger.info('Creating/updating risk assessments for k3s workloads')
        utils.workload_risks_vulns()
        logger.info('Creating/updating risk assessments for IT systems')
        if options['active']:
            it_systems = ITSystem.objects.filter(**ITSystem.ACTIVE_FILTER)
        else:
            it_systems = ITSystem.objects.all()
        utils.itsystem_risks_infra_location(it_systems)
        utils.itsystem_risks_critical_function(it_systems)
        utils.itsystem_risks_backups(it_systems)
        utils.itsystem_risks_support(it_systems)
        utils.itsystem_risks_access(it_systems)
        utils.itsystem_risks_traffic(it_systems)
        logger.info('Complete')
