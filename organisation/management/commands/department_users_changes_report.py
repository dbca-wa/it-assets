from datetime import datetime, date, time, timedelta
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError
from tempfile import NamedTemporaryFile

from organisation.models import AscenderActionLog
from organisation.reports import user_changes_export


class Command(BaseCommand):
    help = "Emails a report of department user changes for the nominated number of days"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            action="store",
            default=7,
            type=int,
            help="Number of days into the past to report user changes",
            dest="days",
        )
        parser.add_argument(
            "--emails",
            action="store",
            default=None,
            type=str,
            help="Comma-separated list of emails to which to deliver the report",
            dest="emails",
        )

    def handle(self, *args, **options):
        if options["emails"]:
            try:
                recipients = options["emails"].split(",")
            except ValueError:
                raise CommandError("Invalid emails value: {} (use comma-separated string)".format(options["emails"]))
        else:
            raise CommandError("Email(s) value is required")

        from_date = date.today() - timedelta(days=options["days"])
        # Turn the date into a TZ-aware datetime to avoid the warning nag.
        from_date = datetime.combine(from_date, time(0, 0)).astimezone(settings.TZ)
        subject = "Department user changes starting {}".format(from_date.strftime("%A, %d %b %Y"))
        action_logs = AscenderActionLog.objects.filter(
            created__gte=from_date,
            level="INFO",
        )
        prefix = f"department_user_changes_{from_date.date().isoformat()}_"
        suffix = ".xlsx"
        tempfile = NamedTemporaryFile(prefix=prefix, suffix=suffix)
        # Write the report output to the temp file.
        user_changes_export(tempfile, action_logs)
        tempfile.flush()

        msg = EmailMultiAlternatives(
            subject=subject,
            from_email=settings.NOREPLY_EMAIL,
            to=recipients,
        )
        msg.attach_file(tempfile.name)
        msg.send()
