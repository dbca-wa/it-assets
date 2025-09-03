import csv
import logging
import os
from tempfile import NamedTemporaryFile

import paramiko
from django.core.management.base import BaseCommand

from organisation.models import DepartmentUser


class Command(BaseCommand):
    help = "Generates a CSV containing user data that should be updated in Ascender and uploads it to SFTP"

    def handle(self, *args, **options):
        logger = logging.getLogger("organisation")
        logger.info("Generating CSV of department user data")
        users = DepartmentUser.objects.filter(employee_id__isnull=False).order_by("employee_id")

        # Convert the queryset to a file stream of CSV data.
        data = NamedTemporaryFile(mode="+w")
        writer = csv.writer(data, quoting=csv.QUOTE_ALL)
        writer.writerow(["EMPLOYEE_ID", "EMAIL", "ACTIVE", "WORK_TELEPHONE", "LICENCE_TYPE"])
        for user in users:
            writer.writerow(
                [
                    user.employee_id,
                    user.email.lower(),
                    user.active,
                    user.telephone,
                    user.get_licence(),
                ]
            )
        data.flush()
        data.seek(0)

        # SFTP credentials
        host = os.getenv("ASCENDER_SFTP_HOSTNAME")
        port = os.getenv("ASCENDER_SFTP_PORT")
        username = os.getenv("ASCENDER_SFTP_USERNAME")
        password = os.getenv("ASCENDER_SFTP_PASSWORD")
        remote_dir = os.getenv("ASCENDER_SFTP_DIRECTORY")

        if not host or not port or not username or not password or not remote_dir:
            raise Exception("Missing required environment variable(s)")

        port = int(port)  # Ensure that port is an integer value.

        # Connect to SFTP
        logger.info("Connecting to Ascender SFTP")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port=port, username=username, password=password)

        sftp = client.open_sftp()
        logger.info("Uploading CSV to Ascender SFTP")
        sftp.put(localpath=data.name, remotepath=f"{remote_dir}/department_users_details.csv")
        sftp.close()
        client.close()
