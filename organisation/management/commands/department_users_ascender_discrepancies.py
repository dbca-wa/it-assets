from data_storage import AzureBlobStorage
from django.core.management.base import BaseCommand
from io import BytesIO
import os
from tempfile import NamedTemporaryFile

from organisation.models import DepartmentUser
from organisation.reports import department_user_ascender_discrepancies


class Command(BaseCommand):
    help = 'Generates an Excel spreadsheet containing discrepancies between department user and Ascender data and uploads to Azure blob storage'

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
        self.stdout.write('Generating discrepancies between department user and Ascender data')
        users = DepartmentUser.objects.all()
        spreadsheet = department_user_ascender_discrepancies(BytesIO(), users)
        f = NamedTemporaryFile()
        f.write(spreadsheet.getbuffer())

        self.stdout.write('Uploading discrepancies to Azure blob storage')
        connect_string = os.environ.get('AZURE_CONNECTION_STRING')
        store = AzureBlobStorage(connect_string, options['container'])
        store.upload_file(options['path'], f.name)

        self.stdout.write(self.style.SUCCESS('Completed'))
