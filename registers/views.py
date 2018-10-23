from datetime import date
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.views.generic import View, ListView, DetailView, CreateView, UpdateView
from pytz import timezone
import xlsxwriter

from .models import Incident, ChangeRequest
from .forms import ChangeRequestCreateForm, ChangeRequestUpdateForm


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


class ChangeRequestList(ListView):
    model = ChangeRequest


class ChangeRequestDetail(DetailView):
    model = ChangeRequest


class ChangeRequestCreate(CreateView):
    model = ChangeRequest
    form_class = ChangeRequestCreateForm

    def get_context_data(self, **kwargs):
        context = super(ChangeRequestCreate, self).get_context_data(**kwargs)
        context['title'] = 'Create a draft change request'
        return context


class ChangeRequestUpdate(UpdateView):
    """View for all changes to an RFC: update, submit, approve, etc.
    """
    model = ChangeRequest
    form_class = ChangeRequestUpdateForm

    def get_context_data(self, **kwargs):
        context = super(ChangeRequestUpdate, self).get_context_data(**kwargs)
        context['title'] = 'Update draft change request {}'.format(self.get_object().pk)
        return context

    def form_valid(self, form):
        self.object = form.save()
        errors = False

        # If the user clicked "submit" (for approval), undertake additional form validation.
        if self.request.POST.get('submit'):
            # If a standard change, this must be selected.
            if self.object.is_standard_change and not self.object.standard_change:
                form.add_error('standard_change', 'Standard change must be selected.')
                errors = True
                # NOTE: standard change will bypass several of the business rules below.
            # Requester is required.
            if not self.object.requester:
                form.add_error('requester', 'Requester cannot be blank.')
                errors = True
            # Approver is required.
            if not self.object.approver:
                form.add_error('approver', 'Approver cannot be blank.')
                errors = True
            # Implementer is required.
            if not self.object.implementer:
                form.add_error('implementer', 'Implementer cannot be blank.')
                errors = True
            # Test date is required if not a standard change.
            if not self.object.is_standard_change and not self.object.test_date:
                form.add_error('test_date', 'Test date must be specified.')
                errors = True
            # Planned start is required.
            if not self.object.planned_start:
                form.add_error('planned_start', 'Planned start time must be specified.')
                errors = True
            # Planned end is required.
            if not self.object.planned_end:
                form.add_error('planned_end', 'Planned end time must be specified.')
                errors = True
            # Either implementation text or upload is required if not a standard change.
            if not self.object.is_standard_change and (not self.object.implementation and not self.object.implementation_docs):
                form.add_error('implementation', 'Implementation instructions must be specified (instructions, document upload or both).')
                form.add_error('implementation_docs', 'See above.')
                errors = True
            # Communication is required if not a standard change.
            if not self.object.is_standard_change and not self.object.communication:
                form.add_error('communication', 'Details relating to any communications must be specified (or input "NA").')
                errors = True

        if errors:
            return super(ChangeRequestUpdate, self).form_invalid(form)

        # TODO: implement workflow for submission for approval.
        return super(ChangeRequestUpdate, self).form_valid(form)
