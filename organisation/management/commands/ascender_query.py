from django.core.management.base import BaseCommand
from organisation.ascender import ascender_employee_fetch
from pprint import pprint


class Command(BaseCommand):
    help = "Query Ascender database by employee ID for staff job records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--employee-id",
            action="store",
            required=True,
            type=str,
            dest="employee_id",
            help="Ascender employee no.",
        )

    def handle(self, *args, **options):
        print("Querying Ascender")
        employee_id, jobs = ascender_employee_fetch(options["employee_id"])

        if not jobs:
            print("No data")

        pprint(jobs)
