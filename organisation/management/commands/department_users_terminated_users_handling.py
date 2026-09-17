import logging
from datetime import date

from django.core.management.base import BaseCommand
from django.conf import settings

from organisation.models import DepartmentUser


class Command(BaseCommand):
    help = "Checks department users for any terminated users, identifies which are beyond the designated grace period, then removes their licenses"

    def add_arguments(self, parser):
        parser.add_argument(
            "-r",
            "--remove-licenses",
            action="store_true",
            dest="remove_licenses",
            help="(Optional) Flag to remove licenses from terminated users who are past the grace period (default behaviour is logging only)",
        )
        parser.add_argument(
            "--days-terminated",
            action="store",
            type=int,
            dest="terminated_account_days",
            help=f"(Optional) Number of days grace for terminated users prior to termination processing (default {settings.TERMINATED_ACCOUNT_DAYS} days)",
        )

    def handle(self, *args, **options):
        logger = logging.getLogger("organisation")
        logger.info("Started termination processing")

        # Default value in settings, may be overidden.
        terminated_account_days = settings.TERMINATED_ACCOUNT_DAYS
        if options.get("terminated_account_days") is not None:
            terminated_account_days = options["terminated_account_days"]

        all_users = DepartmentUser.objects.all()
        users = all_users.exclude(term_date_data__iexact="[]")  # All users with non-blank termination date records

        # Init stat-tracking variables
        all_users_count = len(all_users)
        users_count = len(users)
        past_term_count = 0
        past_grace_period_count = 0
        processed_user_count = 0

        # Iterate through users w/ TERM_DATE records, stripping licenses of users past the termination grace period.
        for user in users:
            # If user is terminated
            if user.past_term_date():
                past_term_count += 1
                days_past_term = (date.today() - user.get_term_date()).days
                # If the user is X days past their termination date, where X is the the terminated account tolerance.
                if days_past_term >= terminated_account_days:
                    past_grace_period_count += 1
                    logger.info(f"user {str(user)} - {days_past_term - terminated_account_days} day(s) past grace period")
                    if options.get("remove_licenses"):
                        logger.info(f"user {str(user)} - Removing Licenses")
                        # Note : Logging and stat tracking here should also track errors. This must be expanded upon when updating remove_licenses().
                        remove_licenses(user)
                        processed_user_count += 1

        logger.info(f"""Terminationed processing complete
SUMMARY:
- {users_count}/{all_users_count} users have actionable TERM_DATE records
- {past_term_count}/{past_grace_period_count} terminated users are over the {terminated_account_days} day grace period
- {processed_user_count}/{past_grace_period_count} accounts succesfully actioned""")


# Stub method - Licenses assignment will move to using groups soon, so this will change pretty soon
# Notes:
# - Should have some way of tracking users that have already been processed and quantifying that
# - Maybe at this point the users can also be deleted from IT Assets? Will follow up w/ Ash on this.
def remove_licenses(self, user):
    pass
