from django.core.management.base import BaseCommand
import logging
from io import BytesIO

from organisation.models import DepartmentUser
from organisation.utils import department_user_ascender_sync, upload_blob


class Command(BaseCommand):
    help = 'Generates a CSV containing user data that should be updated in Ascender and uploads it to Azure blob storage'

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
        users = DepartmentUser.objects.filter(employee_id__isnull=False).order_by('employee_id')
        data = department_user_ascender_sync(users)
        f = BytesIO()
        f.write(data.getbuffer())
        f.flush()
        f.seek(0)

        logger.info('Uploading CSV to Azure blob storage')
        upload_blob(f, options['container'], options['path'])
