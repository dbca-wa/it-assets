from django.core.management.base import BaseCommand, CommandError
from rancher.models import ContainerImage


class Command(BaseCommand):
    help = 'Scans the Docker image of Deployment Workloads for reported vulnerabilities'

    def handle(self, *args, **options):
        # Scan Deployment workloads, but not those in the System project.
        try:
            images = ContainerImage.objects.filter(scan_status__in=(ContainerImage.NOT_SCANED,ContainerImage.SCAN_FAILED)
            for image in images:
                print('Scanning {} image ({})'.format(image,image.imageid))
                image.scan(commit=True)
        except:
            raise CommandError('Workload image scanning failed')
