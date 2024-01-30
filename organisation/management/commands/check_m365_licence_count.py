from django.conf import settings
from django.core import mail
from django.core.management.base import BaseCommand, CommandError
import logging

from itassets.utils import ms_graph_client_token
from organisation.microsoft_products import MS_PRODUCTS
from organisation.utils import ms_graph_subscribed_sku


class Command(BaseCommand):
    help = 'Checks Microsoft 365 product licence availability and sends a notification email when availability drops too low'

    def add_arguments(self, parser):
        parser.add_argument(
            '--emails',
            action='store',
            default=None,
            type=str,
            help='Comma-separated list of emails to which to send the notification (defaults to OIM Service Desk)',
            dest='emails',
        )
        parser.add_argument(
            '--threshold',
            action='store',
            default=None,
            type=int,
            help='Number of available licences at which to send the notification (default 5)',
            dest='threshold',
        )

    def handle(self, *args, **options):
        logger = logging.getLogger('organisation')

        if options['emails']:
            try:
                recipients = options['emails'].split(',')
            except ValueError:
                raise CommandError('Invalid emails value: {} (use comma-separated string)'.format(options['emails']))
        else:
            recipients = [settings.SERVICE_DESK_EMAIL]

        if options['threshold']:
            threshold = options['threshold']
        else:
            threshold = settings.LICENCE_NOTIFY_THRESHOLD

        # M365 license availability is obtained from the subscribedSku resource type.
        # Total license number is returned in the prepaidUnits object (enabled + warning + suspended + lockedOut).
        # License consumption is returned in the value for consumedUnits, but this includes suspended
        # and locked-out licenses.
        # License availabilty (to assign to a user) is not especially intuitive; only licenses having
        # status `enabled` or `warning` are available to be assigned. Therefore if the value of consumedUnits
        # is greater than the value of prepaidUnits (enabled + warning), no licenses are currently
        # available to be assigned.
        # References:
        # - https://learn.microsoft.com/en-us/graph/api/resources/subscribedsku?view=graph-rest-1.0
        # - https://github.com/microsoftgraph/microsoft-graph-docs-contrib/issues/2337

        send_notification = False
        logger.info("Checking Microsoft 365 license availability")
        token = ms_graph_client_token()

        e5_sku = ms_graph_subscribed_sku(MS_PRODUCTS["MICROSOFT 365 E5"], token)
        e5_consumed = e5_sku["consumedUnits"]
        e5_assignable = e5_sku["prepaidUnits"]["enabled"] + e5_sku["prepaidUnits"]["warning"]
        e5_available = e5_assignable - e5_consumed
        if e5_available <= threshold:
            send_notification = True
        if e5_available < 0:
            e5_available = 0

        f3_sku = ms_graph_subscribed_sku(MS_PRODUCTS["MICROSOFT 365 F3"], token)
        f3_consumed = f3_sku["consumedUnits"]
        f3_assignable = f3_sku["prepaidUnits"]["enabled"] + f3_sku["prepaidUnits"]["warning"]
        f3_available = f3_assignable - f3_consumed
        if f3_available <= threshold:
            send_notification = True
        if f3_available < 0:
            f3_available = 0

        eo_sku = ms_graph_subscribed_sku(MS_PRODUCTS["EXCHANGE ONLINE (PLAN 2)"], token)
        eo_consumed = eo_sku["consumedUnits"]
        eo_assignable = eo_sku["prepaidUnits"]["enabled"] + eo_sku["prepaidUnits"]["warning"]
        eo_available = eo_assignable - eo_consumed
        if eo_available <= threshold:
            send_notification = True
        if eo_available < 0:
            eo_available = 0

        sec_sku = ms_graph_subscribed_sku(MS_PRODUCTS["MICROSOFT 365 SECURITY AND COMPLIANCE FOR FLW"], token)
        sec_consumed = sec_sku["consumedUnits"]
        sec_assignable = sec_sku["prepaidUnits"]["enabled"] + sec_sku["prepaidUnits"]["warning"]
        sec_available = sec_assignable - sec_consumed
        if sec_available <= threshold:
            send_notification = True
        if sec_available < 0:
            sec_available = 0

        subject = f"Notification - Microsoft M365 licence availability has reached warning threshold ({threshold})"
        message = f"""This is an automated notification regarding low Microsoft 365 licence availability:\n\n
        Microsoft 365 E5 (On-premise): {e5_consumed} assigned, {e5_available} available\n\n
        Microsoft 365 F3 (Cloud): {f3_consumed} assigned, {f3_available} available\n
        Exchange Online (Plan 2): {eo_consumed} assigned, {eo_available} available\n
        Microsoft 365 Security and Compliance for Firstline Workers: {sec_consumed} assigned, {sec_available} available\n
        """
        html_message = f"""<p>This is an automated notification regarding low Microsoft 365 licence availability:</p>
        <ul>
        <li>Microsoft 365 E5 (On-premise): {e5_consumed} assigned, {e5_available} available</li>
        <li>Microsoft 365 F3 (Cloud): {f3_consumed} assigned, {f3_available} available</li>
        <li>Exchange Online (Plan 2): {eo_consumed} assigned, {eo_available} available</li>
        <li>Microsoft 365 Security and Compliance for Firstline Workers: {sec_consumed} assigned, {sec_available} available</li>
        </ul>"""

        if send_notification:
            logger.info(subject)
            mail.send_mail(
                subject=subject,
                message=message,
                from_email=settings.NOREPLY_EMAIL,
                recipient_list=recipients,
                html_message=html_message,
            )
        else:
            logger.info("No warning notification required")
