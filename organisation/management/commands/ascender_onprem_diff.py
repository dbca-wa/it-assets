from data_storage import AzureBlobStorage
from django.core.management.base import BaseCommand
from django.db.models import Q
import json
import logging
import os
from tempfile import NamedTemporaryFile

from organisation.models import DepartmentUser
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
        logger = logging.getLogger('organisation')
        logger.info('Generating diff between Ascender and on-premise AD data')
        queryset = DepartmentUser.objects.filter(employee_id__isnull=False, ascender_data__isnull=False, ad_guid__isnull=False, ad_data__isnull=False)
        queryset = queryset.exclude(Q(ad_data={}) | Q(ascender_data={}))  # Exclude users with no AD data or no Ascender data.
        discrepancies = ascender_onprem_ad_data_diff(queryset)
        f = NamedTemporaryFile()
        f.write(json.dumps(discrepancies, indent=2).encode('utf-8'))

        logger.info('Uploading diff JSON to Azure blob storage')
        connect_string = os.environ.get('AZURE_CONNECTION_STRING')
        store = AzureBlobStorage(connect_string, options['container'])
        store.upload_file(options['path'], f.name)

        logger.info('Completed')
