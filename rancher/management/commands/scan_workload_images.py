from django.core.management.base import BaseCommand, CommandError
from rancher.models import Workload


class Command(BaseCommand):
    help = 'Scans the image of each Deployment workload for reported vulnerabilities'

    def handle(self, *args, **options):
        # Scan Deployment workloads, but not those in the System project.
        try:
            workloads = Workload.objects.filter(kind='Deployment').exclude(project__name='System')
            for workload in workloads:
                print('Scanning {} image'.format(workload))
                if workload.image_scan():
                    print('{} scanned'.format(workload.image))
                else:
                    print('{} not scanned'.format(workload.image))
        except:
            raise CommandError('Workload image scanning failed')
