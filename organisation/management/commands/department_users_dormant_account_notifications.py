import logging
from datetime import date, timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.utils import timezone

from organisation.models import DepartmentUser


class Command(BaseCommand):
    help = "Checks department users associated with an active licenced account, identifies those which are dormant, and sends warning notification emails to line managers or CCMs."

    def add_arguments(self, parser):
        parser.add_argument(
            "-e",
            "--send-email",
            action="store_true",
            dest="send_email",
            help="(Optional) Flag to send notification emails to managers (default behaviour is logging only)",
        )
        parser.add_argument(
            "-d",
            "--days-prior",
            action="store",
            type=str,
            dest="days_prior",
            help="(Optional) Comma-seperated list of integers, the no. of days prior to deadline on which to send email (default 14,7)",
        )
        parser.add_argument(
            "--days-dormant",
            action="store",
            type=int,
            dest="dormant_account_days",
            help=f"(Optional) Number of days after which an account is considered dormant (default {settings.DORMANT_ACCOUNT_DAYS} days)",
        )

    def handle(self, *args, **options):
        logger = logging.getLogger("organisation")

        # Default value in settings, may be overidden.
        dormant_account_days = settings.DORMANT_ACCOUNT_DAYS
        if options["dormant_account_days"]:
            dormant_account_days = options["dormant_account_days"]

        # Get a list of active, licenced accounts for which we have a 'last sign-in' value.
        active_users = [du for du in DepartmentUser.objects.filter(active=True, last_signin__isnull=False) if du.get_licence()]
        active_users_without_signin = [
            du
            for du in DepartmentUser.objects.filter(active=True, last_signin__isnull=True, last_password_change__isnull=False)
            if du.get_licence()
        ]
        now = timezone.localtime()

        # Parse the days_prior list values.
        if options["days_prior"]:
            try:
                days_prior = [int(i) for i in options["days_prior"].split(",")]
            except ValueError:
                logger.error(
                    f"Invalid value for --days-prior: {options['days_prior']} (provide a comma-seperated list of integer values without spaces)"
                )
                return
        else:
            days_prior = [14, 7]

        logger.info(f"Reviewing department users for dormant licenced accounts ({dormant_account_days} days without sign-in)")

        # Send warning notification emails to the manager n days prior to the account becoming dormant.
        for day in days_prior:
            days_before_dormant = dormant_account_days - day

            # Check users with sign-in data.
            for du in active_users:
                last_signin_days_ago = (now - du.last_signin).days
                deadline = date.today() + timedelta(days=day)
                if last_signin_days_ago == days_before_dormant:
                    if du.manager:
                        recipient = du.manager
                    elif du.cost_centre and du.cost_centre.manager:
                        recipient = du.cost_centre.manager
                    else:
                        recipient = None

                    if recipient:
                        if options["send_email"]:
                            logger.info(f"Sending {day}-day notification email to {recipient.email} regarding {du.email}")
                            self.send_notification_email(recipient, du, last_signin_days_ago, dormant_account_days, deadline)
                        else:
                            logger.info(f"{day}-day notification email to {recipient.email} regarding {du.email} not sent")
                    else:
                        logger.warning(
                            f"No manager/CCM recipient recorded for {du.email} ({du.cost_centre.code}), {day}-day notification email not sent"
                        )

            # Check users without sign-in data (use password last change date).
            for du in active_users_without_signin:
                last_signin_days_ago = (now - du.last_password_change).days
                deadline = date.today() + timedelta(days=day)
                if last_signin_days_ago == days_before_dormant:
                    if du.manager:
                        recipient = du.manager
                    elif du.cost_centre and du.cost_centre.manager:
                        recipient = du.cost_centre.manager
                    else:
                        recipient = None

                    if recipient:
                        if options["send_email"]:
                            logger.info(f"Sending {day}-day notification email to {recipient.email} regarding {du.email}")
                            self.send_notification_email(recipient, du, last_signin_days_ago, dormant_account_days, deadline)
                        else:
                            logger.info(f"{day}-day notification email to {recipient.email} regarding {du.email} not sent")
                    else:
                        logger.warning(
                            f"No manager/CCM recipient recorded for {du.email} ({du.cost_centre.code}), {day}-day notification email not sent"
                        )
        logger.info("Complete")

    def send_notification_email(self, recipient, du, last_signin_days_ago, dormant_account_days, deadline):
        text_content = f"""Hi {recipient.given_name},\n
This is an automated notification email to let you know that the Microsoft 365 account below has not been logged into for {last_signin_days_ago} days.
OIM will automatically deactivate accounts that have not been logged into for {dormant_account_days} days, which may impact business processes.\n
Name: {du.name}
Email: {du.email}
Title: {du.title}
Last sign-in: {du.last_signin.strftime('%d/%b/%Y') if du.last_signin else 'Unknown'}
Manager: {du.manager.name if du.manager else ''}\n
If the account is still required for business use, please ensure that the staff member logs into the account prior to {deadline.strftime('%d/%b/%Y')}.\n
Regards,
OIM Service Desk\n"""
        html_content = f"""<p>Hi {recipient.given_name},</p>
<p>This is an automated notification email to let you know that the Microsoft 365 account below has not been logged into for {last_signin_days_ago} days.
OIM will automatically deactivate accounts that have not been logged into for {dormant_account_days} days, which may impact business processes.</p>
<ul>
<li>Name: {du.name}</li>
<li>Email: {du.email}</li>
<li>Title: {du.title}</li>
<li>Last sign-in: {du.last_signin.strftime('%d/%b/%Y') if du.last_signin else 'Unknown'}</li>
<li>Manager: {du.manager.name if du.manager else ''}</li>
</ul>
<p>If the account is still required for business use, please ensure that the staff member logs into the account prior to {deadline.strftime('%d/%b/%Y')}.</p>
<p>Regards,</p>
<p>OIM Service Desk</p>"""
        subject = f"Dormant account notification - {du.name}"
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.NOREPLY_EMAIL,
            to=[recipient.email],
            bcc=[settings.SECURITY_EMAIL],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        return
