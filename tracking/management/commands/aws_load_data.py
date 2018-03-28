from django.core.management.base import BaseCommand
from tracking.utils_aws import aws_load_instances


class Command(BaseCommand):
    help = 'Loads EC2 instance information.'

    def handle(self, *args, **options):
        aws_load_instances()
