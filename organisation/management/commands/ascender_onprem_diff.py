from data_storage import AzureBlobStorage
from django.core.management.base import BaseCommand
from organisation.utils import ascender_onprem_ad_data_diff
import json
import os


class Command(BaseCommand):
    help = 'Generates a diff file between Ascender and on-premise AD data and uploads to Azure blob storage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--container',
            action='store',
            dest='container',
            required=True,
            help='Azure container name'
        )
        parser.add_argument(
            '--json_path',
            action='store',
            dest='json_path',
            required=True,
            help='JSON output file path'
        )

    def handle(self, *args, **options):
        self.stdout.write('Generating diff between Ascender and on-premise AD data')
        discrepancies = ascender_onprem_ad_data_diff()
        f = open('/tmp/discrepancies.json', 'w')
        f.write(json.dumps(discrepancies, indent=4))
        f.close()

        self.stdout.write('Uploading diff JSON to Azure blob storage')
        connect_string = os.environ.get('AZURE_CONNECTION_STRING')
        store = AzureBlobStorage(connect_string, options['container'])
        store.upload_file(options['json_path'], '/tmp/discrepancies.json')

        self.stdout.write(self.style.SUCCESS('Completed'))
