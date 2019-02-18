from datetime import date, timedelta
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from registers.models import ChangeRequest
from texttable import Texttable


class Command(BaseCommand):
    help = 'Emails the current change calendar to users in the "CAB members" group'

    def handle(self, *args, **options):
        # Determine the current week's RFCs.
        d = date.today()
        week_start = d - timedelta(days=d.weekday())
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
            rows.append(
                [
                    rfc.pk,
                    rfc.title,
                    rfc.get_change_type_display(),
                    rfc.get_status_display(),
                    rfc.requester.get_full_name(),
                    rfc.endorser.get_full_name(),
                    rfc.implementer.get_full_name(),
                    '{}\n{}'.format(rfc.planned_start.strftime('%A, %d-%b-%Y %H:%M'), rfc.planned_end.strftime('%A, %d-%b-%Y %H:%M'))
                ]
            )
        table.add_rows(rows, header=True)
        text_content = table.draw()

        # Email the CAB members group.
        if not Group.objects.filter(name='CAB members').exists():
            raise CommandError('"CAB members" group does not exist.')
        cab = Group.objects.get(name='CAB members')
        subject = 'Change requests for week starting {}'.format(week_start.isoformat())
        recipients = list(User.objects.filter(groups__in=[cab], is_active=True).values_list('email', flat=True))
        msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, recipients)
        msg.attach_alternative(html_content, 'text/html')
        msg.send()
