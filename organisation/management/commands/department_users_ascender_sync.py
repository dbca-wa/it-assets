from data_storage import AzureBlobStorage
from django.core.management.base import BaseCommand
import logging
import os
from tempfile import NamedTemporaryFile

from organisation.models import DepartmentUser
from organisation.utils import department_user_ascender_sync


class Command(BaseCommand):
    help = 'Generates a CSV containing user data that should be updated in Ascender'

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
            help='Upload file path'
        )

    def handle(self, *args, **options):
        logger = logging.getLogger('organisation')
        logger.info('Generating CSV of department user data')
        users = DepartmentUser.objects.filter(
            employee_id__isnull=False,
            telephone__isnull=False,
        ).exclude(telephone='').order_by('employee_id')
        data = department_user_ascender_sync(users)
        f = NamedTemporaryFile()
        f.write(data.getbuffer())

        logger.info('Uploading CSV to Azure blob storage')
        connect_string = os.environ.get('AZURE_CONNECTION_STRING')
        store = AzureBlobStorage(connect_string, options['container'])
        store.upload_file(options['path'], f.name)
