from data_storage import AzureBlobStorage
from django.core.management.base import BaseCommand
import json
import os
from tempfile import NamedTemporaryFile

from organisation.utils import ascender_onprem_ad_data_diff


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
            '--path',
            action='store',
            dest='path',
            required=True,
            help='JSON upload path'
        )

    def handle(self, *args, **options):
        self.stdout.write('Generating diff between Ascender and on-premise AD data')
        discrepancies = ascender_onprem_ad_data_diff()
        f = NamedTemporaryFile()
        f.write(json.dumps(discrepancies, indent=4).encode('utf-8'))

        self.stdout.write('Uploading diff JSON to Azure blob storage')
        connect_string = os.environ.get('AZURE_CONNECTION_STRING')
        store = AzureBlobStorage(connect_string, options['container'])
        store.upload_file(options['path'], f.name)

        self.stdout.write(self.style.SUCCESS('Completed'))
