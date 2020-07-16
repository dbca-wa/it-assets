from django.core.management.base import BaseCommand, CommandError
from rancher.models import Workload


class Command(BaseCommand):
    help = 'Scans the Docker image of Deployment Workloads for reported vulnerabilities'

    def handle(self, *args, **options):
        # Scan Deployment workloads, but not those in the System project.
        try:
            workloads = Workload.objects.filter(kind='Deployment', image__isnull=False).exclude(project__name='System')
            for workload in workloads:
                print('Scanning {} image ({})'.format(workload, workload.image))
                result = workload.image_scan()
                if result[0]:
                    print('Scan complete')
                else:
                    print('Scan incomplete'.format(workload.image))
                    print(result[1])
        except:
            raise CommandError('Workload image scanning failed')
