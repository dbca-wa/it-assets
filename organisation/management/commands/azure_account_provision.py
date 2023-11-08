from django.core.management.base import BaseCommand
import logging
from organisation.ascender import ascender_user_import


class Command(BaseCommand):
    help = "Manually provision a new Azure account for an Ascender record, optionally ignoring normal creation rules"

    def add_arguments(self, parser):
        parser.add_argument(
            "--employee-id",
            action="store",
            required=True,
            type=str,
            dest="employee_id",
            help="Ascender employee no.",
        )
        parser.add_argument(
            "--ignore-job-start-date",
            action="store_true",
            dest="ignore_job_start_date",
            help="Ignore restriction related to job starting date",
        )

    def handle(self, *args, **options):
        logger = logging.getLogger("organisation")

        logger.info(f"Provisioning Azure user account for Ascender employee ID {options['employee_id']}")
        if "ignore_job_start_date" in options and options["ignore_job_start_date"]:
            logger.info("Ignoring job start date restriction")
            user = ascender_user_import(options["employee_id"], True)
        else:
            user = ascender_user_import(options["employee_id"])

        if user:
            logger.info(f"Azure user account for {user.email} provisioned")
        else:
            logger.info("Azure user account not provisioned")
