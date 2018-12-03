from datetime import date, datetime, timedelta
from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.http import HttpResponse, HttpResponseRedirect
from django.views.generic import View, ListView, DetailView, CreateView, UpdateView
from organisation.models import DepartmentUser
from pytz import timezone
import xlsxwriter

from .models import Incident, ChangeRequest, ChangeLog
from .forms import ChangeRequestCreateForm, ChangeRequestUpdateForm, ChangeRequestEndorseForm, ChangeRequestCompleteForm


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
    paginate_by = 20

    def get_queryset(self):
        queryset = super(ChangeRequestList, self).get_queryset()
        if 'q' in self.request.GET and self.request.GET['q']:
            query = self.request.GET['q'].strip()
            queryset = queryset.filter(title__icontains=query)
        return queryset


class ChangeRequestDetail(DetailView):
    model = ChangeRequest

    def get_context_data(self, **kwargs):
        context = super(ChangeRequestDetail, self).get_context_data(**kwargs)
        rfc = self.get_object()
        tz = timezone(settings.TIME_ZONE)
        context['may_complete'] = rfc.is_ready and self.request.user.email in [rfc.requester.email, rfc.implementer.email] and rfc.planned_end <= datetime.now().astimezone(tz)
        return context


class ChangeRequestCreate(CreateView):
    model = ChangeRequest
    form_class = ChangeRequestCreateForm

    def get_context_data(self, **kwargs):
        context = super(ChangeRequestCreate, self).get_context_data(**kwargs)
        context['title'] = 'Create a draft change request'
        return context

    def get_initial(self):
        initial = super(ChangeRequestCreate, self).get_initial()
        # Try setting the requester to equal the request user.
        if DepartmentUser.objects.filter(email=self.request.user.email).exists():
            initial['requester'] = DepartmentUser.objects.get(email=self.request.user.email)
        return initial


class ChangeRequestUpdate(UpdateView):
    """View for all end-user changes to an RFC: update, submit, endorse, etc.
    """
    model = ChangeRequest
    form_class = ChangeRequestUpdateForm

    def get(self, request, *args, **kwargs):
        # Validate that the RFC may still be updated.
        rfc = self.get_object()
        if not rfc.is_draft:
            # Redirect to the object detail view.
            return HttpResponseRedirect(rfc.get_absolute_url())
        return super(ChangeRequestUpdate, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ChangeRequestUpdate, self).get_context_data(**kwargs)
        context['title'] = 'Update draft change request {}'.format(self.get_object().pk)
        return context

    def get_success_url(self):
        return self.get_object().get_absolute_url()

    def form_valid(self, form):
        rfc = form.save()
        errors = False

        # If the user clicked "submit" (for approval), undertake additional form validation.
        if self.request.POST.get('submit'):
            # If a standard change, this must be selected.
            if rfc.is_standard_change and not rfc.standard_change:
                form.add_error('standard_change', 'Standard change must be selected.')
                errors = True
                # NOTE: standard change will bypass several of the business rules below.
            # Requester is required.
            if not rfc.requester:
                form.add_error('requester', 'Requester cannot be blank.')
                errors = True
            # Approver is required.
            if not rfc.approver:
                form.add_error('approver', 'Approver cannot be blank.')
                errors = True
            # Implementer is required.
            if not rfc.implementer:
                form.add_error('implementer', 'Implementer cannot be blank.')
                errors = True
            # Test date is required if not a standard change.
            if not rfc.is_standard_change and not rfc.test_date:
                form.add_error('test_date', 'Test date must be specified.')
                errors = True
            # Planned start is required.
            if not rfc.planned_start:
                form.add_error('planned_start', 'Planned start time must be specified.')
                errors = True
            # Planned end is required.
            if not rfc.planned_end:
                form.add_error('planned_end', 'Planned end time must be specified.')
                errors = True
            # Either implementation text or upload is required if not a standard change.
            if not rfc.is_standard_change and (not rfc.implementation and not rfc.implementation_docs):
                form.add_error('implementation', 'Implementation instructions must be specified (instructions, document upload or both).')
                form.add_error('implementation_docs', 'See above.')
                errors = True
            # Communication is required if not a standard change.
            if not rfc.is_standard_change and not rfc.communication:
                form.add_error('communication', 'Details relating to any communications must be specified (or input "NA").')
                errors = True
            # No validation errors: change the RFC status, send an email to the approver and make a log.
            if not errors:
                # TODO: send an email to the requester.
                rfc.status = 1
                rfc.save()
                msg = 'Change request {} submitted for endorsement by {}.'.format(rfc.pk, self.request.user.get_full_name())
                messages.success(self.request, msg)
                log = ChangeLog(change_request=rfc, log=msg)
                log.save()
                rfc.email_approver(self.request)
                log = ChangeLog(
                    change_request=rfc, log='Request for approval emailed to {}.'.format(rfc.approver.get_full_name()))
                log.save()

        if errors:
            return super(ChangeRequestUpdate, self).form_invalid(form)
        return super(ChangeRequestUpdate, self).form_valid(form)


class ChangeRequestEndorse(UpdateView):
    model = ChangeRequest
    form_class = ChangeRequestEndorseForm
    template_name = 'registers/changerequest_endorse.html'

    def get_context_data(self, **kwargs):
        context = super(ChangeRequestEndorse, self).get_context_data(**kwargs)
        context['title'] = 'Endorse change request {}'.format(self.get_object().pk)
        return context

    def get(self, request, *args, **kwargs):
        # Validate that the RFC may be endorsed.
        rfc = self.get_object()
        if not rfc.is_submitted:
            # Redirect to the object detail view.
            messages.warning(self.request, 'Change request {} is not ready for endorsement.'.format(rfc.pk))
            return HttpResponseRedirect(rfc.get_absolute_url())
        if self.request.user.email != rfc.approver.email:
            messages.warning(self.request, 'You are not the approver for change request {}.'.format(rfc.pk))
            return HttpResponseRedirect(rfc.get_absolute_url())
        return super(ChangeRequestEndorse, self).get(request, *args, **kwargs)

    def form_valid(self, form):
        rfc = form.save()

        if self.request.POST.get('endorse'):
            # If the user clicked "Endorse", log this and change status to Scheduled.
            rfc.status = 2
            rfc.save()
            msg = 'Change request {} has been endorsed by {}; it is now scheduled to be assessed at CAB.'.format(rfc.pk, self.request.user.get_full_name())
            messages.success(self.request, msg)
            log = ChangeLog(change_request=rfc, log=msg)
            log.save()
            # Send an email to the requester.
            subject = 'Change request {} has been endorsed'.format(rfc.pk)
            detail_url = self.request.build_absolute_uri(rfc.get_absolute_url())
            text_content = """This is an automated message to let you know that change request
                {} ("{}") has been endorsed by {}, and it is now scheduled to be approved at the
                next OIM Change Advisory Board meeting.\n
                {}\n
                """.format(rfc.pk, rfc.title, rfc.approver.get_full_name(), detail_url)
            html_content = """<p>This is an automated message to let you know that change request
                {0} ("{1}") has been endorsed by {2}, and it is now scheduled to be approved at the
                next OIM Change Advisory Board meeting.</p>
                <ul><li><a href="{3}">{3}</a></li></ul>
                """.format(rfc.pk, rfc.title, rfc.approver.get_full_name(), detail_url)
            msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, [rfc.requester.email])
            msg.attach_alternative(html_content, 'text/html')
            msg.send()
        elif self.request.POST.get('reject'):
            # If the user clicked "Reject", log this and change status back to Draft.
            rfc.status = 0
            rfc.save()
            msg = 'Change request {} has been rejected by {}; status has been reset to Draft.'.format(rfc.pk, self.request.user.get_full_name())
            messages.warning(self.request, msg)
            log = ChangeLog(change_request=rfc, log=msg)
            log.save()
            # Send an email to the requester.
            subject = 'Change request {} has been rejected'.format(rfc.pk)
            detail_url = self.request.build_absolute_uri(rfc.get_absolute_url())
            text_content = """This is an automated message to let you know that change request
                {} ("{}") has been rejected by {}. Its status has been reset to "Draft" for updates
                and re-submission.\n
                {}\n
                """.format(rfc.pk, rfc.title, rfc.approver.get_full_name(), detail_url)
            html_content = """<p>This is an automated message to let you know that change request
                {0} ("{1}") has been rejected by {2}. Its status has been reset to "Draft" for updates
                and re-submission.</p>
                <ul><li><a href="{3}">{3}</a></li></ul>
                """.format(rfc.pk, rfc.title, rfc.approver.get_full_name(), detail_url)
            msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, [rfc.requester.email])
            msg.attach_alternative(html_content, 'text/html')
            msg.send()
        return super(ChangeRequestEndorse, self).form_valid(form)


class ChangeRequestExport(View):
    """A custom view to export all Incident values to an Excel spreadsheet.
    """
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=change_requests_{}.xlsx'.format(date.today().isoformat())

        with xlsxwriter.Workbook(
            response,
            {
                'in_memory': True,
                'default_date_format': 'dd-mmm-yyyy HH:MM',
                'remove_timezone': True,
            },
        ) as workbook:
            rfcs = ChangeRequest.objects.all()
            changes = workbook.add_worksheet('Change requests')
            changes.write_row('A1', (
                'Change ref.', 'Title', 'Change type', 'Requester', 'Approver', 'Implementer', 'Status',
                'Test date', 'Planned start', 'Planned end', 'Completed', 'Outage duration',
                'System(s) affected', 'Incident URL',
            ))
            row = 1
            tz = timezone(settings.TIME_ZONE)
            for i in rfcs:
                changes.write_row(row, 0, [
                    i.pk, i.title, i.get_change_type_display(), i.requester.get_full_name(),
                    i.approver.get_full_name(), i.implementer.get_full_name(),
                    i.get_status_display(), i.test_date,
                    i.planned_start.astimezone(tz) if i.planned_start else '',
                    i.planned_end.astimezone(tz) if i.planned_end else '',
                    i.completed.astimezone(tz) if i.completed else '',
                    str(i.outage) if i.outage else '', i.systems_affected, i.incident_url,
                ])
                row += 1
            changes.set_column('A:A', 11)
            changes.set_column('B:B', 44)
            changes.set_column('C:C', 12)
            changes.set_column('D:F', 18)
            changes.set_column('G:G', 26)
            changes.set_column('H:K', 18)
            changes.set_column('L:L', 15)
            changes.set_column('M:N', 30)

        return response


class ChangeRequestCalendar(ListView):
    # TODO: refactor the calendar to show a weeks-worth of changes.
    model = ChangeRequest
    template_name = 'registers/changerequest_calendar.html'

    def get_date_param(self, **kwargs):
        if 'date' in self.kwargs:
            # Parse the date YYYY-MM-DD
            return datetime.strptime(self.kwargs['date'], '%Y-%m-%d').date()
        else:
            return date.today()

    def get_context_data(self, **kwargs):
        context = super(ChangeRequestCalendar, self).get_context_data(**kwargs)
        context['date'] = self.get_date_param()
        context['date_yesterday'] = self.get_date_param() - timedelta(1)
        context['date_tomorrow'] = self.get_date_param() + timedelta(1)
        return context

    def get_queryset(self):
        queryset = super(ChangeRequestCalendar, self).get_queryset()
        d = self.get_date_param()
        return queryset.filter(planned_start__date=d).order_by('planned_start')


class ChangeRequestComplete(UpdateView):
    """View for all 'completion' changes to an RFC: success/failure/notes etc.
    """
    model = ChangeRequest
    form_class = ChangeRequestCompleteForm
    template_name = 'registers/changerequest_complete.html'

    def get(self, request, *args, **kwargs):
        rfc = self.get_object()
        # Validate that the RFC may be completed.
        if not rfc.is_ready:
            # Redirect to the detail view.
            messages.warning(self.request, 'Change request {} is not ready for completion.'.format(rfc.pk))
            return HttpResponseRedirect(rfc.get_absolute_url())
        # Business rule: only the implementer or requester may complete the change.
        if self.request.user.email not in [rfc.requester.email, rfc.implementer.email]:
            messages.warning(self.request, 'You are not authorised to complete change request {}.'.format(rfc.pk))
            return HttpResponseRedirect(rfc.get_absolute_url())
        return super(ChangeRequestComplete, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ChangeRequestComplete, self).get_context_data(**kwargs)
        context['title'] = 'Complete/finalise change request {}'.format(self.get_object().pk)
        return context

    def get_success_url(self):
        return self.get_object().get_absolute_url()

    def form_valid(self, form):
        rfc = form.save()
        d = form.cleaned_data
        log = ChangeLog(change_request=rfc)

        # Change the RFC status and make a log.
        if d['outcome'] == 'complete':
            rfc.status = 4
            log.log = 'Change {} was marked "Completed successfully" by {}.'.format(rfc.pk, self.request.user.get_full_name())
            messages.success(self.request, 'Change request {} was been marked as completed.'.format(rfc.pk))
        elif d['outcome'] == 'rollback':
            rfc.status = 5
            log.log = 'Change {} was marked "Undertaken and rolled back" by {}.'.format(rfc.pk, self.request.user.get_full_name())
            messages.info(self.request, 'Change request {} was been marked as rolled back.'.format(rfc.pk))
        elif d['outcome'] == 'cancelled':
            rfc.status = 6
            log.log = 'Change {} was marked "Cancelled" by {}.'.format(rfc.pk, self.request.user.get_full_name())
            messages.info(self.request, 'Change request {} was been marked as cancelled.'.format(rfc.pk))
        rfc.save()
        log.save()

        return super(ChangeRequestComplete, self).form_valid(form)
