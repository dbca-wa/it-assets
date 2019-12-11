from datetime import date, datetime, timedelta
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from pytz import timezone
from registers.models import ChangeRequest
from texttable import Texttable


class Command(BaseCommand):
    help = 'Emails the weekly change calendar to users in the "CAB members" group (plus optional additional recipients)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date', action='store', dest='datestring', default=None,
            help='Date from which to start the calendar in format YYYY-MM-DD')
        parser.add_argument(
            '--emails', action='store', dest='emails', default=None,
            help='Comma-separated list of additional emails to which to deliver the report')

    def handle(self, *args, **options):
        d = date.today()
        if options['datestring']:
            try:
                d = datetime.strptime(options['datestring'], '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('Invalid date value: {} (use format YYYY-MM-DD)'.format(options['datestring']))

        emails = None
        if options['emails']:
            try:
                emails = options['emails'].split(',')
            except ValueError:
                raise CommandError('Invalid emails value: {} (use comma-separated string)'.format(options['emails']))

        week_start = datetime.combine(d, datetime.min.time()).astimezone(timezone(settings.TIME_ZONE))
        week_end = week_start + timedelta(days=7)
        rfcs = ChangeRequest.objects.filter(planned_start__range=[week_start, week_end]).order_by('planned_start')

        # Construct the HTML / plaintext email content to send.
        context = {
            'start': week_start,
            'object_list': rfcs,
            'domain': Site.objects.get_current().domain,
        }
        html_content = render_to_string('registers/email_cab_rfc_calendar.html', context)

        table = Texttable(max_width=0)
        table.set_cols_dtype(['i', 't', 't', 't', 't', 't', 't', 't'])
        rows = [['Change ref', 'Title', 'Change type', 'Status', 'Requester', 'Endorser', 'Implementer', 'Planned start & end']]
        for rfc in rfcs:
            # Planned end date field might be blank.
            planned_end = rfc.planned_end.strftime('%A, %d-%b-%Y %H:%M') if rfc.planned_end else ''
            rows.append(
                [
                    rfc.pk,
                    rfc.title,
                    rfc.get_change_type_display(),
                    rfc.get_status_display(),
                    rfc.requester.get_full_name(),
                    rfc.endorser.get_full_name(),
                    rfc.implementer.get_full_name(),
                    '{}\n{}'.format(rfc.planned_start.strftime('%A, %d-%b-%Y %H:%M'), planned_end)
                ]
            )
        table.add_rows(rows, header=True)
        text_content = table.draw()

        # Email the CAB members group.
        if not Group.objects.filter(name='CAB members').exists():
            raise CommandError('"CAB members" group does not exist.')
        cab = Group.objects.get(name='CAB members')
        subject = 'Weekly change calendar starting {}'.format(week_start.strftime('%A, %d %b %Y'))
        recipients = list(User.objects.filter(groups__in=[cab], is_active=True).values_list('email', flat=True))

        # Optional additional email recipients.
        if emails:
            recipients = recipients + emails

        msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, recipients)
        msg.attach_alternative(html_content, 'text/html')
        msg.send()
