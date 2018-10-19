from datetime import date
from django.conf import settings
from django.http import HttpResponse
from django.views.generic import View, ListView, DetailView, TemplateView
from pytz import timezone
import xlsxwriter

from .models import Incident, ChangeRequest


class IncidentList(ListView):
    paginate_by = 20

    def get_queryset(self):
        # By default, return ongoing incidents only.
        if 'all' in self.request.GET:
            return Incident.objects.all()
        return Incident.objects.filter(resolution__isnull=True)


class IncidentDetail(DetailView):
    model = Incident


class IncidentExport(View):
    """A custom view to export all Incident values to an Excel spreadsheet.
    """
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=incident_register_{}.xlsx'.format(date.today().isoformat())

        with xlsxwriter.Workbook(
            response,
            {
                'in_memory': True,
                'default_date_format': 'dd-mmm-yyyy HH:MM',
                'remove_timezone': True,
            },
        ) as workbook:
            # Incident Register worksheet
            incidents = Incident.objects.all()
            register = workbook.add_worksheet('Incident register')
            register.write_row('A1', (
                'Incident no.', 'Status', 'Description', 'Priority', 'Category', 'Start time',
                'Resolution time', 'Duration', 'RTO met', 'System(s) affected', 'Location(s) affected',
                'Incident manager', 'Incident owner', 'Detection method', 'Workaround action(s)',
                'Root cause', 'Remediation action(s)', 'Division(s) affected'
            ))
            row = 1
            tz = timezone(settings.TIME_ZONE)
            for i in incidents:
                register.write_row(row, 0, [
                    i.pk, i.status.capitalize(), i.description, i.get_priority_display(),
                    i.get_category_display(), i.start.astimezone(tz),
                    i.resolution.astimezone(tz) if i.resolution else '',
                    str(i.duration) if i.duration else '', i.rto_met(),
                    i.systems_affected, i.locations_affected,
                    i.manager.get_full_name() if i.manager else '',
                    i.owner.get_full_name() if i.owner else '',
                    i.get_detection_display(), i.workaround, i.root_cause, i.remediation,
                    i.divisions_affected if i.divisions_affected else ''
                ])
                row += 1
            register.set_column('A:A', 11)
            register.set_column('C:C', 72)
            register.set_column('D:D', 13)
            register.set_column('E:E', 18)
            register.set_column('F:G', 16)
            register.set_column('H:H', 13)
            register.set_column('I:I', 8)
            register.set_column('J:K', 28)
            register.set_column('L:M', 16)
            register.set_column('N:N', 20)
            register.set_column('O:R', 24)

        return response


class ChangeRequestList(TemplateView):
    template_name = 'changerequestlist.html'


class ChangeRequestDetail(DetailView):
    model = ChangeRequest


class ChangeRequestCreate(TemplateView):
    template_name = 'changerequest.html'
