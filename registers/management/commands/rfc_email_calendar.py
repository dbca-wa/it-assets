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
    help = 'Emails a calendar of scheduled RFCs to users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            action='store',
            default=None,
            type=str,
            help='Date from which to start the calendar in format YYYY-MM-DD',
            dest='start_date',
        )
        parser.add_argument(
            '--days',
            action='store',
            default=7,
            type=int,
            help='Number of days that the calendar should include',
            dest='days',
        )
        parser.add_argument(
            '--cab-members',
            action='store_true',
            help='Deliver the calendar to CAB members',
            dest='cab_members',
        )
        parser.add_argument(
            '--emails',
            action='store',
            default=None,
            type=str,
            help='Comma-separated list of emails to which to deliver the calendar',
            dest='emails',
        )
        parser.add_argument(
            '--all-rfcs',
            action='store_true',
            help='Change calendar to contain RFCs having all status types, not just those relevant to CAB',
            dest='all_rfcs',
        )
        parser.add_argument(
            '--scheduled',
            action='store_true',
            help='Change calendar to contain RFCs having only "Scheduled for CAB" status',
            dest='scheduled',
        )
        parser.add_argument(
            '--ready',
            action='store_true',
            help='Change calendar to contain RFCs having only "Ready for implementation" status',
            dest='ready',
        )

    def handle(self, *args, **options):
        try:
            d = date.today()
            if options['start_date']:
                try:
                    d = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
                except ValueError:
                    raise CommandError('Invalid date value: {} (use format YYYY-MM-DD)'.format(options['start_date']))

            emails = None
            if options['emails']:
                try:
                    emails = options['emails'].split(',')
                except ValueError:
                    raise CommandError('Invalid emails value: {} (use comma-separated string)'.format(options['emails']))

            start_date = datetime.combine(d, datetime.min.time()).astimezone(timezone(settings.TIME_ZONE))
            end_date = start_date + timedelta(days=options['days'])

            if 'all_rfcs' in options and options['all_rfcs']:
                rfcs = ChangeRequest.objects.filter(planned_start__range=[start_date, end_date]).order_by('planned_start')
            elif 'scheduled' in options and options['scheduled']:
                rfcs = ChangeRequest.objects.filter(planned_start__range=[start_date, end_date], status=2).order_by('planned_start')
            elif 'ready' in options and options['ready']:
                rfcs = ChangeRequest.objects.filter(planned_start__range=[start_date, end_date], status=3).order_by('planned_start')
            else:
                rfcs = ChangeRequest.objects.filter(planned_start__range=[start_date, end_date], status__in=[2, 3]).order_by('planned_start')

            if Site.objects.filter(name='Change Requests').exists():
                domain = Site.objects.get(name='Change Requests').domain
            else:
                domain = Site.objects.get_current().domain
            if domain.startswith('http://'):
                domain = domain.replace('http', 'https')
            if not domain.startswith('https://'):
                domain = 'https://' + domain

            # Construct the HTML and plaintext email content to send.
            context = {
                'start': start_date,
                'end': end_date,
                'object_list': rfcs,
                'domain': domain,
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
                        rfc.requester.name if rfc.requester else '',
                        rfc.endorser.name if rfc.endorser else '',
                        rfc.implementer.name if rfc.implementer else '',
                        '{}\n{}'.format(rfc.planned_start.strftime('%A, %d-%b-%Y %H:%M'), planned_end)
                    ]
                )
            table.add_rows(rows, header=True)
            text_content = table.draw()

            subject = 'Change calendar starting {}'.format(start_date.strftime('%A, %d %b %Y'))
            recipients = []

            # Email the CAB members group.
            if options['cab_members']:
                if not Group.objects.filter(name='CAB members').exists():
                    raise CommandError('"CAB members" group does not exist.')
                cab = Group.objects.get(name='CAB members')
                recipients = recipients + list(User.objects.filter(groups__in=[cab], is_active=True).values_list('email', flat=True))

            # Additional email recipients.
            if emails:
                recipients = recipients + emails

            recipients = set(recipients)

            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.NOREPLY_EMAIL,
                to=recipients,
            )
            msg.attach_alternative(html_content, 'text/html')
            msg.send()
        except Exception as ex:
            error = 'IT Assets email RFC calendar raised an exception at {}'.format(datetime.now().astimezone(timezone(settings.TIME_ZONE)).isoformat())
            text_content = 'Exception:\n\n{}'.format(ex)
            if not settings.DEBUG:
                # Send an email to ADMINS.
                msg = EmailMultiAlternatives(
                    subject=error,
                    body=text_content,
                    from_email=settings.NOREPLY_EMAIL,
                    to=settings.ADMINS,
                )
                msg.send()
            raise CommandError(error)
