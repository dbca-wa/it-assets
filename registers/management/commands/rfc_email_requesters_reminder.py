from datetime import datetime
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from pytz import timezone
from registers.models import ChangeRequest, ChangeLog


class Command(BaseCommand):
    help = 'Emails requesters a reminder to record completion of any outstanding change requests.'

    def handle(self, *args, **options):
        # All changes of status "Ready", where the planned_end datetime has passed and completed datetime is null:
        rfcs = ChangeRequest.objects.filter(
            status=3, planned_end__lte=datetime.now().astimezone(timezone(settings.TIME_ZONE)), completed__isnull=True)

        if rfcs.count() > 0:
            for rfc in rfcs:
                if rfc.requester:
                    subject = 'Completion of change request {}'.format(rfc)
                    text_content = """This is an automated message to let you know that you are recorded as the
                        requester for change request {}, scheduled to be undertaken on {}.\n
                        Please visit the following URL and record the outcome of the change in order to finalise it:\n
                        {}\n
                        """.format(rfc, rfc.planned_start.astimezone().strftime('%d/%b/%Y at %H:%M'), rfc.get_absolute_url())
                    html_content = """<p>This is an automated message to let you know that you are recorded as the
                        requester for change request {0}, scheduled to be undertaken on {1}.</p>
                        <p>Please visit the following URL and record the outcome of the change in order to finalise it:</p>
                        <ul><li><a href="{2}">{2}</a></li></ul>
                        """.format(rfc, rfc.planned_start.astimezone().strftime('%d/%b/%Y at %H:%M'), rfc.get_absolute_url())
                    msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, [rfc.requester.email])
                    msg.attach_alternative(html_content, 'text/html')
                    msg.send()

                    # Create changelog
                    msg = '''Reminder of incomplete change: {} sent to assigned requester {} on {}
                        '''.format(rfc, rfc.requester.get_full_name(), datetime.now().astimezone().strftime('%d/%b/%Y at %H:%M'))
                    log = ChangeLog(change_request=rfc, log=msg)
                    log.save()
