from datetime import date
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError
import tempfile

from registers.models import ITSystem
from registers.reports import itsr_staff_discrepancies


class Command(BaseCommand):
    help = 'Emails an IT System Register discrepancy report to the specified recipients'

    def add_arguments(self, parser):
        parser.add_argument(
            '--emails', action='store', dest='emails', default=None,
            help='Comma-separated list of email recipients')

    def handle(self, *args, **options):
        emails = None
        if options['emails']:
            try:
                emails = options['emails'].split(',')
            except ValueError:
                raise CommandError('Invalid emails value: {} (use comma-separated string)'.format(options['emails']))
        else:
            raise CommandError('Comma-separated list of email recipients is required)')

        html_content = '<p>The attached report contains any detected discrepancies in active systems in the IT System Register.</p>'
        text_content = 'The attached report contains any detected discrepancies in active systems in the IT System Register.'
        subject = 'IT System Register discrepancy report - {}'.format(date.today().strftime('%d %b %Y'))
        it_systems = ITSystem.objects.filter(**ITSystem.ACTIVE_FILTER)
        content = tempfile.TemporaryFile()
        content = itsr_staff_discrepancies(content, it_systems)
        content.seek(0)

        msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, emails)
        msg.attach_alternative(html_content, 'text/html')
        msg.attach('it_system_discrepancies_{}.xlsx'.format(date.today().isoformat()), content.read(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        msg.send()
