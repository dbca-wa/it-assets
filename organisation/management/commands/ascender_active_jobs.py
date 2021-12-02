from datetime import datetime
from data_storage import AzureBlobStorage
from django.core.management.base import BaseCommand
import json
import logging
import os
from tempfile import NamedTemporaryFile

from organisation.ascender import ascender_employee_fetch
from organisation.models import DepartmentUser


class Command(BaseCommand):
    help = 'Generates a list of staff having current jobs in Ascender and active AD accounts, then uploads this to Azure blob storage'

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
        logger.info('Generating list of staff having active Ascender jobs')

        ascender_jobs = {}
        ascender_data = ascender_employee_fetch()
        for eid, jobs in ascender_data:
            # Discard FPC staff.
            if jobs[0]['clevel1_id'] != 'FPC':
                ascender_jobs[eid] = jobs[0]

        today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        jobs_active = []
        jobs_terminated = []
        for job in ascender_jobs.values():
            if 'job_term_date' in job and job['job_term_date']:
                job_term_date = datetime.strptime(job['job_term_date'], '%Y-%m-%d')
                if job_term_date < today:
                    jobs_terminated.append(job)
                    continue
            jobs_active.append(job)

        emp_ids = [job['employee_id'] for job in jobs_active]
        departmentusers_active_job = DepartmentUser.objects.filter(employee_id__in=emp_ids)  # These are department users with an "active" job in Ascender.
        jobs = [{'employee_id': acct.employee_id, 'azure_guid': acct.azure_guid, 'email': acct.email, 'name': acct.get_full_name()} for acct in departmentusers_active_job]

        logger.info('Uploading active jobs JSON to Azure blob storage')
        f = NamedTemporaryFile()
        f.write(json.dumps(jobs, indent=2).encode('utf-8'))
        connect_string = os.environ.get('AZURE_CONNECTION_STRING')
        store = AzureBlobStorage(connect_string, options['container'])
        store.upload_file(options['path'], f.name)

        logger.info('Completed')
