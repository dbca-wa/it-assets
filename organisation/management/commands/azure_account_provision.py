import logging

from django.core.management.base import BaseCommand

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
        parser.add_argument(
            "--manager-override-email",
            action="store",
            type=str,
            dest="manager_override_email",
            help="Override the manager in Ascender in favour of using the supplied email",
        )
        parser.add_argument(
            "--position-no",
            action="store",
            type=str,
            dest="position_no",
            help="Manually define the position number to which the employee belongs",
        )

    def handle(self, *args, **options):
        logger = logging.getLogger("organisation")
        logger.info(f"Provisioning Azure user account for Ascender employee ID {options['employee_id']}")

        employee_id = options["employee_id"]
        ignore_job_start_date = False
        manager_override_email = None
        position_no = None

        if "ignore_job_start_date" in options and options["ignore_job_start_date"]:
            ignore_job_start_date = True
            logger.info("Ignoring job start date restriction")

        if "manager_override_email" in options and options["manager_override_email"]:
            manager_override_email = options["manager_override_email"]
            logger.info(f"Overriding manager, using email {manager_override_email}")

        if "position_no" in options and options["position_no"]:
            position_no = options["position_no"]
            logger.info(f"Using position number {position_no}")

        new_user = ascender_user_import(
            employee_id, ignore_job_start_date=ignore_job_start_date, manager_override_email=manager_override_email, position_no=position_no
        )

        if new_user:
            logger.info(f"Azure user account for {new_user.email} provisioned")
        else:
            logger.info("Azure user account not provisioned")
