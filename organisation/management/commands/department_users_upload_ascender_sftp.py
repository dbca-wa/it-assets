from django.core.management.base import BaseCommand
import logging
import os
import pysftp

from organisation.models import DepartmentUser
from organisation.utils import department_user_ascender_sync


class Command(BaseCommand):
    help = "Generates a CSV containing user data that should be updated in Ascender and uploads it to SFTP"

    def handle(self, *args, **options):
        logger = logging.getLogger("organisation")
        logger.info("Generating CSV of department user data")
        users = DepartmentUser.objects.filter(employee_id__isnull=False).order_by("employee_id")
        data = department_user_ascender_sync(users)

        host = os.environ.get("ASCENDER_SFTP_HOSTNAME")
        port = int(os.environ.get("ASCENDER_SFTP_PORT"))
        username = os.environ.get("ASCENDER_SFTP_USERNAME")
        password = os.environ.get("ASCENDER_SFTP_PASSWORD")
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None
        logger.info("Connecting to Ascender SFTP")
        sftp = pysftp.Connection(host=host, port=port, username=username, password=password, cnopts=cnopts)
        dir = os.environ.get("ASCENDER_SFTP_DIRECTORY")
        sftp.chdir(dir)
        logger.info("Uploading CSV to Ascender SFTP")
        sftp.putfo(data, remotepath="department_users_details.csv")
        sftp.close()
