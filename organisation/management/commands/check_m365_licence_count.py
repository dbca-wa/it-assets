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

        send_notification = False
        logger.info("Checking Microsoft 365 license availability")
        token = ms_graph_client_token()

        e5_sku = ms_graph_subscribed_sku(MS_PRODUCTS['MICROSOFT 365 E5'], token)
        e5_total = e5_sku["prepaidUnits"]["enabled"] + e5_sku["prepaidUnits"]["suspended"] + e5_sku["prepaidUnits"]["warning"]
        e5_consumed = e5_sku['consumedUnits']
        if e5_total - e5_consumed <= threshold:
            send_notification = True

        f3_sku = ms_graph_subscribed_sku(MS_PRODUCTS['MICROSOFT 365 F3'], token)
        f3_total = f3_sku["prepaidUnits"]["enabled"] + f3_sku["prepaidUnits"]["suspended"] + f3_sku["prepaidUnits"]["warning"]
        f3_consumed = f3_sku['consumedUnits']
        if f3_total - f3_consumed <= threshold:
            send_notification = True

        eo_sku = ms_graph_subscribed_sku(MS_PRODUCTS['EXCHANGE ONLINE (PLAN 2)'], token)
        eo_total = eo_sku["prepaidUnits"]["enabled"] + eo_sku["prepaidUnits"]["suspended"] + eo_sku["prepaidUnits"]["warning"]
        eo_consumed = eo_sku['consumedUnits']
        if eo_total - eo_consumed <= threshold:
            send_notification = True

        sec_sku = ms_graph_subscribed_sku(MS_PRODUCTS['MICROSOFT 365 SECURITY AND COMPLIANCE FOR FLW'], token)
        sec_total = sec_sku["prepaidUnits"]["enabled"] + sec_sku["prepaidUnits"]["suspended"] + sec_sku["prepaidUnits"]["warning"]
        sec_consumed = sec_sku['consumedUnits']
        if sec_total - sec_consumed <= threshold:
            send_notification = True

        subject = f"Notification - Microsoft M365 licence availability has dropped to warning threshold ({threshold})"
        message = f"""This is an automated notification regarding Microsoft 365 licence usage availability. User account licence consumption:\n\n
        Microsoft 365 E5 (On-premise): {e5_consumed} / {e5_total}\n\n
        Microsoft 365 F3 (Cloud): {f3_consumed} / {f3_total}\n
        Exchange Online (Plan 2): {eo_consumed} / {eo_total}\n
        Microsoft 365 Security and Compliance for Firstline Workers: {sec_consumed} / {sec_total}\n
        """
        html_message = f"""<p>This is an automated notification regarding Microsoft 365 licence usage availability. User account licence consumption:</p>
        <ul>
        <li>Microsoft 365 E5 (On-premise): {e5_consumed} / {e5_total}</li>
        <li>Microsoft 365 F3 (Cloud): {f3_consumed} / {f3_total}</li>
        <li>Exchange Online (Plan 2): {eo_consumed} / {eo_total}</li>
        <li>Microsoft 365 Security and Compliance for Firstline Workers: {sec_consumed} / {sec_total}</li>
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
