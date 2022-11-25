from calendar import monthrange
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.urls import reverse
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views.generic import View, ListView, DetailView, CreateView, UpdateView, TemplateView
from pytz import timezone
import re

from bigpicture.models import RISK_CATEGORY_CHOICES
from itassets.utils import breadcrumbs_list
from organisation.models import DepartmentUser
from .models import ITSystem, ChangeRequest, ChangeLog, StandardChange
from .forms import (
    ChangeRequestCreateForm, StandardChangeRequestCreateForm, ChangeRequestChangeForm,
    StandardChangeRequestChangeForm, ChangeRequestEndorseForm, ChangeRequestCompleteForm,
    EmergencyChangeRequestForm, ChangeRequestApprovalForm, ChangeRequestSMEReviewForm,
)
from .reports import change_request_export, riskassessment_export
from .utils import search_filter

TZ = timezone(settings.TIME_ZONE)


class ITSystemAPIResource(View):
    """An API view that returns JSON of current IT Systems.
    """
    def get(self, request, *args, **kwargs):
        queryset = ITSystem.objects.filter(
            status__in=[0, 2],
        ).prefetch_related(
            'cost_centre',
            'owner',
            'technology_custodian',
            'information_custodian',
        )

        # Queryset filtering.
        if 'pk' in kwargs and kwargs['pk']:  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs['pk'])
        if 'q' in self.request.GET:  # Allow basic filtering on name or system ID
            queryset = queryset.filter(
                Q(name__icontains=self.request.GET['q']) |
                Q(system_id=self.request.GET['q'])
            )

        # Tailor the API response.
        if 'selectlist' in request.GET:  # Smaller response, for use in HTML select lists.
            systems = [{'id': system.pk, 'text': system.name} for system in queryset]
        else:  # Normal API response.
            systems = [
                {
                    'id': system.pk,
                    'name': system.name,
                    'system_id': system.system_id,
                    'status': system.get_status_display(),
                    'link': system.link,
                    'description': system.description,
                    'cost_centre': system.cost_centre.code if system.cost_centre else None,
                    'owner': system.owner.name if system.owner else None,
                    'technology_custodian': system.technology_custodian.name if system.technology_custodian else None,
                    'information_custodian': system.information_custodian.name if system.information_custodian else None,
                    'availability': system.get_availability_display() if system.availability else None,
                    'seasonality': system.get_seasonality_display() if system.seasonality else None,
                } for system in queryset
            ]

        return JsonResponse(systems, safe=False)


class ChangeRequestList(LoginRequiredMixin, ListView):
    model = ChangeRequest
    paginate_by = 20

    def get_queryset(self):
        if 'mine' in self.request.GET:
            email = self.request.user.email
            qs = super().get_queryset().filter(requester__email__iexact=email).distinct()
        elif 'q' in self.request.GET and self.request.GET['q']:
            from .admin import ChangeRequestAdmin
            q = search_filter(ChangeRequestAdmin.search_fields, self.request.GET['q'])
            qs = super().get_queryset().filter(q).distinct()
        else:
            # Exclude cancelled RFCs with no planned start date so they don't clutter the first page.
            qs = super().get_queryset().exclude(status=6, planned_start__isnull=True)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass in any query string
        context['site_title'] = 'DBCA Office of Information Management'
        context['site_acronym'] = 'OIM'
        context['page_title'] = 'Change request register'
        # Breadcrumb links:
        links = [(None, 'Change request register')]
        context['breadcrumb_trail'] = breadcrumbs_list(links)
        if 'q' in self.request.GET:
            context['query_string'] = self.request.GET['q']
        return context


class StandardChangeList(LoginRequiredMixin, ListView):
    model = StandardChange
    paginate_by = 100

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_title'] = 'DBCA Office of Information Management'
        context['site_acronym'] = 'OIM'
        context['page_title'] = 'Standard change register'
        # Breadcrumb links:
        links = [(reverse("change_request_list"), "Change request register"), (None, 'Standard changes')]
        context['breadcrumb_trail'] = breadcrumbs_list(links)
        return context


class StandardChangeDetail(LoginRequiredMixin, DetailView):
    model = StandardChange

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        std_change = self.get_object()
        context['site_title'] = 'DBCA Office of Information Management'
        context['site_acronym'] = 'OIM'
        context['page_title'] = 'Standard change #{}'.format(std_change)
        # Breadcrumb links:
        links = [(reverse("change_request_list"), "Change request register"), (reverse("standard_change_list"), 'Standard changes'), (None, std_change.pk)]
        context['breadcrumb_trail'] = breadcrumbs_list(links)
        # Context variables that determine if determine is certain template elements are displayed.
        emails = []
        if std_change.endorser:
            emails.append(std_change.endorser.email.lower())
        context['user_authorised'] = self.request.user.email.lower() in [emails] or self.request.user.is_staff is True
        return context


class ChangeRequestDetail(LoginRequiredMixin, DetailView):
    model = ChangeRequest

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rfc = self.get_object()
        context['site_title'] = 'DBCA Office of Information Management'
        context['site_acronym'] = 'OIM'
        context['page_title'] = 'Change request #{}'.format(rfc)
        # Breadcrumb links:
        links = [(reverse("change_request_list"), "Change request register"), (None, rfc.pk)]
        context['breadcrumb_trail'] = breadcrumbs_list(links)

        context['may_complete'] = (
            rfc.is_ready and
            self.request.user.email.lower() in [rfc.requester.email.lower(), rfc.implementer.email.lower()] and
            rfc.planned_end <= datetime.now().astimezone(TZ)
        )
        # Context variables that determines if determine is certain template elements are displayed.
        if rfc.requester:
            context['is_requester'] = self.request.user.email.lower() == rfc.requester.email.lower()
        else:
            context['is_requester'] = False
        if rfc.endorser:
            context['is_endorser'] = self.request.user.email.lower() == rfc.endorser.email.lower()
        else:
            context['is_endorser'] = False
        if rfc.sme:
            context['is_sme'] = self.request.user.email.lower() == rfc.sme.email.lower()
        else:
            context['is_sme'] = False
        emails = []
        if rfc.requester:
            emails.append(rfc.requester.email.lower())
        if rfc.endorser:
            emails.append(rfc.endorser.email.lower())
        if rfc.implementer:
            emails.append(rfc.implementer.email.lower())
        context['user_authorised'] = self.request.user.email.lower() in [emails] or self.request.user.is_staff is True

        # Certain functions should only be available to Change Managers (or superusers):
        context['user_is_change_manager'] = self.request.user.groups.filter(name='Change Managers').exists()
        return context


class ChangeRequestCreate(LoginRequiredMixin, CreateView):
    model = ChangeRequest

    def get_form_class(self):
        if 'std' in self.kwargs and self.kwargs['std']:
            return StandardChangeRequestCreateForm
        elif 'emerg' in self.kwargs and self.kwargs['emerg']:
            return EmergencyChangeRequestForm
        return ChangeRequestCreateForm

    def get_initial(self):
        initial = super().get_initial()
        if 'std' in self.kwargs and self.kwargs['std'] and 'id' in self.request.GET and self.request.GET['id']:
            if StandardChange.objects.filter(pk=self.request.GET["id"]).exists():
                initial["standard_change"] = StandardChange.objects.get(pk=self.request.GET["id"])
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_title'] = 'DBCA Office of Information Management'
        context['site_acronym'] = 'OIM'
        if 'std' in self.kwargs and self.kwargs['std']:
            context['page_title'] = 'Create a draft standard change request'
        elif 'emerg' in self.kwargs and self.kwargs['emerg']:
            context['page_title'] = 'Create an emergency change request'
        else:
            context['page_title'] = 'Create a draft change request'
        # Breadcrumb links:
        links = [(None, 'Change request register'), ()]
        links = [(reverse("change_request_list"), "Change request register"), (None, context['page_title'])]
        context['breadcrumb_trail'] = breadcrumbs_list(links)
        return context

    def post(self, request, *args, **kwargs):
        # If the user clicked Cancel, redirect back to the RFC list view.
        if request.POST.get("cancel"):
            return HttpResponseRedirect(reverse('change_request_list'))
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        rfc = form.save(commit=False)
        # Set the requester as the request user (email match case-insensitive).
        if DepartmentUser.objects.filter(email__iexact=self.request.user.email).exists():
            rfc.requester = DepartmentUser.objects.get(email__iexact=self.request.user.email)
        # Set the endorser, implementer and SME (if required).
        if self.request.POST.get('endorser_choice'):
            rfc.endorser = DepartmentUser.objects.get(pk=int(self.request.POST.get('endorser_choice')))
        if self.request.POST.get('implementer_choice'):
            rfc.implementer = DepartmentUser.objects.get(pk=int(self.request.POST.get('implementer_choice')))
        if self.request.POST.get('sme_choice'):
            rfc.sme = DepartmentUser.objects.get(pk=int(self.request.POST.get('sme_choice')))
        # Autocomplete normal/standard change fields.
        if 'std' in self.kwargs and self.kwargs['std']:
            rfc.change_type = 1
            rfc.endorser = rfc.standard_change.endorser
            rfc.implementation = rfc.standard_change.implementation
            rfc.description = rfc.standard_change.description
        elif 'emerg' in self.kwargs and self.kwargs['emerg']:
            rfc.change_type = 2
            if rfc.completed:  # If a completion date was recorded, set the status as "Completed".
                rfc.status = 4
            else:  # Otherwise, just set the status to "Scheduled for CAB".
                rfc.status = 2
        else:
            rfc.change_type = 0
        rfc.save()
        messages.success(self.request, 'Change request {} has been created.'.format(rfc.pk))
        if 'std' in self.kwargs and self.kwargs['std']:
            # Must be carried out after save()
            rfc.it_systems.set(rfc.standard_change.it_systems.all())
        return super().form_valid(form)


class ChangeRequestChange(LoginRequiredMixin, UpdateView):
    """View for all end-user changes to an RFC: update, submit, endorse, etc.
    """
    model = ChangeRequest

    def get(self, request, *args, **kwargs):
        # Validate that the RFC may still be updated.
        rfc = self.get_object()
        if not rfc.is_draft:
            # Redirect to the object detail view.
            return HttpResponseRedirect(rfc.get_absolute_url())
        return super().get(request, *args, **kwargs)

    def get_form_class(self):
        rfc = self.get_object()
        if rfc.is_standard_change:
            return StandardChangeRequestChangeForm
        elif rfc.is_emergency_change:
            return EmergencyChangeRequestForm
        return ChangeRequestChangeForm

    def get_form(self, *args, **kwargs):
        form = super().get_form(*args, **kwargs)
        rfc = self.get_object()
        if rfc.endorser and not rfc.is_standard_change:
            form.fields['endorser_choice'].choices = [(rfc.endorser.pk, rfc.endorser.email)]
        if rfc.implementer:
            form.fields['implementer_choice'].choices = [(rfc.implementer.pk, rfc.implementer.email)]
        if rfc.sme:
            form.fields['sme_choice'].choices = [(rfc.sme.pk, rfc.sme.email)]
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_title'] = 'DBCA Office of Information Management'
        context['site_acronym'] = 'OIM'
        rfc = self.get_object()
        if rfc.is_standard_change:
            context['page_title'] = 'Update draft standard change request {}'.format(rfc.pk)
        else:
            context['page_title'] = 'Update draft change request {}'.format(rfc.pk)
        # Breadcrumb links:
        links = [
            (reverse("change_request_list"), "Change request register"),
            (reverse("change_request_detail", args=(rfc.pk,)), rfc.pk),
            (None, "Update")
        ]
        context['breadcrumb_trail'] = breadcrumbs_list(links)
        return context

    def get_success_url(self):
        return self.get_object().get_absolute_url()

    def post(self, request, *args, **kwargs):
        # If the user clicked Cancel, redirect back to the RFC detail view.
        if request.POST.get("cancel"):
            return HttpResponseRedirect(self.get_object().get_absolute_url())
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        rfc = form.save(commit=False)
        # Set the endorser, implementer and SME (if required).
        if self.request.POST.get('endorser_choice'):
            rfc.endorser = DepartmentUser.objects.get(pk=int(self.request.POST.get('endorser_choice')))
        if self.request.POST.get('implementer_choice'):
            rfc.implementer = DepartmentUser.objects.get(pk=int(self.request.POST.get('implementer_choice')))
        if self.request.POST.get('sme_choice'):
            rfc.sme = DepartmentUser.objects.get(pk=int(self.request.POST.get('sme_choice')))
        rfc.save()

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
            # Endorser is required for normal changes (not standard changes).
            if rfc.is_normal_change and not rfc.endorser:
                form.add_error('endorser_choice', 'Endorser cannot be blank.')
                errors = True
            # Implementer is required.
            if not rfc.implementer:
                form.add_error('implementer_choice', 'Implementer cannot be blank.')
                errors = True
            # SME is required for normal changes (not standard changes).
            if rfc.is_normal_change and not rfc.sme:
                form.add_error('sme_choice', 'SME cannot be blank.')
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
            # No validation errors: change the RFC status, send an email to the endorser and make a log.
            if not errors:
                # Standard change workflow: submit directly to CAB.
                if rfc.is_standard_change:
                    rfc.status = 2
                    rfc.save()
                    msg = f"Standard change request {rfc.pk} submitted to CAB by {self.request.user.get_full_name()}."
                    messages.success(self.request, msg)
                    ChangeLog(change_request=rfc, log=msg).save()
                # Normal change workflow: submit for endorsement, then to CAB.
                else:
                    rfc.status = 1
                    rfc.save()
                    rfc.email_endorser()
                    msg = f"Change request {rfc.pk} submitted for endorsement by {self.request.user.get_full_name()}."
                    messages.success(self.request, msg)
                    ChangeLog(change_request=rfc, log=msg).save()
                    ChangeLog(change_request=rfc, log=f"Request for endorsement of change request {rfc.pk} emailed to {rfc.endorser.email}.").save()

        # Emergency RFC changes.
        if self.request.POST.get('save') and rfc.is_emergency_change:
            if rfc.completed:  # If a completed date is recorded, set the status automatically.
                rfc.status = 4
                rfc.save()

        if errors:
            return super().form_invalid(form)
        return super().form_valid(form)


class ChangeRequestEndorse(LoginRequiredMixin, UpdateView):
    """A dual-purpose view, used by the endorser and the SME to endorse/reject an RFC.
    """
    model = ChangeRequest
    form_class = ChangeRequestEndorseForm
    template_name = 'registers/changerequest_endorse.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_title'] = 'DBCA Office of Information Management'
        context['site_acronym'] = 'OIM'
        rfc = self.get_object()
        if rfc.is_submitted:
            context['page_title'] = 'Endorse change request {}'.format(rfc.pk)
            b = 'Endorse'
        elif rfc.is_sme_review:
            context['page_title'] = 'Subject matter expert - endorse change request {}'.format(rfc.pk)
            b = 'SME endorse'
        # Breadcrumb links:
        links = [
            (reverse("change_request_list"), "Change request register"),
            (reverse("change_request_detail", args=(rfc.pk,)), rfc.pk),
            (None, b),
        ]
        context['breadcrumb_trail'] = breadcrumbs_list(links)
        return context

    def get(self, request, *args, **kwargs):
        # Validate that the RFC may be endorsed by the endorser or the SME.
        rfc = self.get_object()
        if not rfc.is_submitted and not rfc.is_sme_review:
            # Redirect to the object detail view.
            messages.warning(self.request, 'Change request {} is not ready for endorsement.'.format(rfc.pk))
            return HttpResponseRedirect(rfc.get_absolute_url())
        if rfc.is_submitted:
            if not rfc.endorser:
                messages.warning(self.request, 'Change request {} has no endorser recorded.'.format(rfc.pk))
                return HttpResponseRedirect(rfc.get_absolute_url())
            if self.request.user.email.lower() != rfc.endorser.email.lower():
                messages.warning(self.request, 'You are not the endorser for change request {}.'.format(rfc.pk))
                return HttpResponseRedirect(rfc.get_absolute_url())
        if rfc.is_sme_review:
            if not rfc.sme:
                messages.warning(self.request, 'Change request {} has no subject matter expert recorded.'.format(rfc.pk))
                return HttpResponseRedirect(rfc.get_absolute_url())
            if self.request.user.email.lower() != rfc.sme.email.lower():
                messages.warning(self.request, 'You are not the subject matter expert for change request {}.'.format(rfc.pk))
                return HttpResponseRedirect(rfc.get_absolute_url())
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        rfc = form.save()

        if Site.objects.filter(name='Change Requests').exists():
            domain = Site.objects.get(name='Change Requests').domain
        else:
            domain = Site.objects.get_current().domain
        if domain.startswith('http://'):
            domain = domain.replace('http', 'https')
        if not domain.startswith('https://'):
            domain = 'https://' + domain
        detail_url = '{}{}'.format(domain, rfc.get_absolute_url())

        if self.request.POST.get('endorse'):
            subject = 'Change request {} has been endorsed'.format(rfc.pk)
            # Case 1 - endorser
            if rfc.is_submitted:
                # If the user clicked "Endorse", log this and change status to "Ready for SME review".
                # The Change Manager will process it further.
                rfc.status = 7
                rfc.save()
                msg = 'Change request {} has been endorsed by {}; it is now with the SME to be reviewed.'.format(rfc.pk, self.request.user.get_full_name())
                messages.success(self.request, msg)
                log = ChangeLog(change_request=rfc, log=msg)
                log.save()
                # Send an email to the requester.
                text_content = """This is an automated message to let you know that change request
                    {} ("{}") has been endorsed by {}, and it is now in review by the OIM Change
                    Manager.\n
                    {}\n
                    """.format(rfc.pk, rfc.title, rfc.endorser.name, detail_url)
                html_content = """<p>This is an automated message to let you know that change request
                    {0} ("{1}") has been endorsed by {2}, and it is now in review by the OIM Change
                    Manager.</p>
                    <ul><li><a href="{3}">{3}</a></li></ul>
                    """.format(rfc.pk, rfc.title, rfc.endorser.name, detail_url)
                msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, [rfc.requester.email])
                msg.attach_alternative(html_content, 'text/html')
                msg.send()

                # Email the Change Manager(s), if they are specified.
                if User.objects.filter(groups__name='Change Managers').exists():
                    text_content = """This is an automated message to let you know that change request
                        {} ("{}") has been endorsed by {}, and you should now review it to determine if
                        subject matter expert review is necessary.\n
                        {}\n
                        """.format(rfc.pk, rfc.title, rfc.endorser.name, detail_url)
                    html_content = """<p>This is an automated message to let you know that change request
                        {0} ("{1}") has been endorsed by {2}, and you should now review it to determine if
                        subject matter expert review is necessary.</p>
                        <ul><li><a href="{3}">{3}</a></li></ul>
                        """.format(rfc.pk, rfc.title, rfc.endorser.name, detail_url)
                    subject = subject + " - Ready for SME review"
                    changeManagers = User.objects.filter(groups__name='Change Managers')
                    msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, [i.email for i in changeManagers])
                    msg.attach_alternative(html_content, 'text/html')
                    msg.send()
            # Case 2 - SME
            elif rfc.is_sme_review:
                # If the user clicked "Endorse", log this and change status to "Scheduled for CAB".
                rfc.status = 2
                rfc.save()
                msg = 'Change request {} has been endorsed by {} as SME; it is now scheduled for CAB.'.format(rfc.pk, self.request.user.get_full_name())
                messages.success(self.request, msg)
                log = ChangeLog(change_request=rfc, log=msg)
                log.save()
                # Email the Change Manager.
                if User.objects.filter(groups__name='Change Managers').exists():
                    text_content = """This is an automated message to let you know that change request
                        {} ("{}") has been endorsed by {} as subject matter expert. It is now schedule for CAB.\n
                        {}\n
                        """.format(rfc.pk, rfc.title, self.request.user.get_full_name(), detail_url)
                    html_content = """<p>This is an automated message to let you know that change request
                        {0} ("{1}") has been endorsed by {2} as subject matter expert. It is now scheduled for CAB.</p>
                        <ul><li><a href="{3}">{3}</a></li></ul>
                        """.format(rfc.pk, rfc.title, self.request.user.get_full_name(), detail_url)
                    subject = subject + " by SME"
                    changeManagers = User.objects.filter(groups__name='Change Managers')
                    msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, [i.email for i in changeManagers])
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
            text_content = """This is an automated message to let you know that change request
                {} ("{}") has been rejected by {}. Its status has been reset to "Draft" for updates
                and re-submission.\n
                {}\n
                """.format(rfc.pk, rfc.title, rfc.endorser.name, detail_url)
            html_content = """<p>This is an automated message to let you know that change request
                {0} ("{1}") has been rejected by {2}. Its status has been reset to "Draft" for updates
                and re-submission.</p>
                <ul><li><a href="{3}">{3}</a></li></ul>
                """.format(rfc.pk, rfc.title, rfc.endorser.name, detail_url)
            msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, [rfc.requester.email])
            msg.attach_alternative(html_content, 'text/html')
            msg.send()
        return super().form_valid(form)


class ChangeRequestSMEReview(LoginRequiredMixin, UpdateView):
    model = ChangeRequest
    form_class = ChangeRequestSMEReviewForm
    template_name = 'registers/changerequest_sme_review.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_title'] = 'DBCA Office of Information Management'
        context['site_acronym'] = 'OIM'
        rfc = self.get_object()
        context['page_title'] = 'Change request {} - SME review'.format(rfc.pk)
        # Breadcrumb links:
        links = [
            (reverse("change_request_list"), "Change request register"),
            (reverse("change_request_detail", args=(rfc.pk,)), rfc.pk),
            (None, "SME review")
        ]
        context['breadcrumb_trail'] = breadcrumbs_list(links)
        return context

    def get(self, request, *args, **kwargs):
        # Validate that the RFC may be reviewed.
        rfc = self.get_object()
        if not rfc.is_sme_review:
            # Redirect to the object detail view.
            messages.warning(self.request, 'Change request {} is not ready for SME review.'.format(rfc.pk))
            return HttpResponseRedirect(rfc.get_absolute_url())
        # Check that user is a Change Manager, or a superuser.
        if not (self.request.user.is_superuser or self.request.user.groups.filter(name='Change Managers').exists()):
            messages.warning(self.request, 'You are not authorised to set SME review for change request {}.'.format(rfc.pk))
            return HttpResponseRedirect(rfc.get_absolute_url())
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # If the user clicked Cancel, redirect back to the RFC detail view.
        if request.POST.get("cancel"):
            return HttpResponseRedirect(self.get_object().get_absolute_url())
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        rfc = self.get_object()
        # Set the SME (if required).
        if self.request.POST.get('sme_choice'):
            rfc.sme = DepartmentUser.objects.get(pk=int(self.request.POST.get('sme_choice')))
        rfc.save()

        # If a SME was set, send an email to that user for review & endorsement.
        if rfc.sme:
            if Site.objects.filter(name='Change Requests').exists():
                domain = Site.objects.get(name='Change Requests').domain
            else:
                domain = Site.objects.get_current().domain
            if domain.startswith('http://'):
                domain = domain.replace('http', 'https')
            if not domain.startswith('https://'):
                domain = 'https://' + domain
            detail_url = '{}{}'.format(domain, rfc.get_absolute_url())

            # Send an email to the SME.
            subject = 'Change request {} - Subject matter expert review request'.format(rfc.pk)
            text_content = """This is an automated message to let you know that you have been
                nominated as the subject matter expert for change request {} ("{}").\n
                Please review the change here to either endorse or reject it:\n
                {}\n
                """.format(rfc.pk, rfc.title, detail_url)
            html_content = """<p>This is an automated message to let you know that you have been
                nominated as the subject matter expert for change request {0} ("{1}").</p>
                <p>Please review the change here to either endorse or reject it:</p>
                <ul><li><a href="{2}">{2}</a></li></ul>
                """.format(rfc.pk, rfc.title, detail_url)
            msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, [rfc.sme.email])
            msg.attach_alternative(html_content, 'text/html')
            msg.send()
            msg = 'Notification sent to {} to undertake SME review of change request {}.'.format(rfc.sme.email, rfc.pk)
            messages.success(self.request, msg)
            log = ChangeLog(change_request=rfc, log=msg)
            log.save()

        else:  # SME was not set, therefore set the status to "Schedule for CAB".
            rfc.status = 2
            rfc.save()
            msg = 'Change request {} has undergone SME review; no SME is required and it is scheduled for CAB.'.format(rfc.pk)
            messages.success(self.request, msg)
            log = ChangeLog(change_request=rfc, log=msg)
            log.save()

        return HttpResponseRedirect(rfc.get_absolute_url())


class ChangeRequestApproval(LoginRequiredMixin, UpdateView):
    form_class = ChangeRequestApprovalForm
    template_name = 'registers/changerequest_approval.html'
    model = ChangeRequest

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_title'] = 'DBCA Office of Information Management'
        context['site_acronym'] = 'OIM'
        rfc = self.get_object()
        context['page_title'] = 'Approve change request {}'.format(rfc.pk)
        # Breadcrumb links:
        links = [
            (reverse("change_request_list"), "Change request register"),
            (reverse("change_request_detail", args=(rfc.pk,)), rfc.pk),
            (None, "Approve")
        ]
        context['breadcrumb_trail'] = breadcrumbs_list(links)
        return context

    def get_success_url(self):
        return reverse('change_request_list')

    def get(self, request, *args, **kwargs):
        # Validate that the RFC may be approved at CAB.
        rfc = self.get_object()
        if not rfc.is_scheduled:
            # Redirect to the object detail view.
            messages.warning(self.request, 'Change request {} is not ready for approval.'.format(rfc.pk))
            return HttpResponseRedirect(rfc.get_absolute_url())
        if not self.request.user.groups.filter(name='CAB members').exists():
            msg = 'You are not logged in as a member of CAB, The action has been cancelled.'
            messages.warning(self.request, msg)
            return HttpResponseRedirect(rfc.get_absolute_url())
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # If the user clicked Cancel, redirect back to the RFC detail view.
        if request.POST.get("cancel"):
            return HttpResponseRedirect(self.get_object().get_absolute_url())
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        rfc = self.get_object()
        rfc.status = 3
        rfc.save()
        logText = 'CAB member approval: change request has been approved by {}.'.format(self.request.user.get_full_name())
        changelog = ChangeLog(change_request=rfc, log=logText)
        changelog.save()
        msg = 'You have approved this change on behalf of CAB'
        messages.success(self.request, msg)

        if Site.objects.filter(name='Change Requests').exists():
            domain = Site.objects.get(name='Change Requests').domain
        else:
            domain = Site.objects.get_current().domain
        if domain.startswith('http://'):
            domain = domain.replace('http', 'https')
        if not domain.startswith('https://'):
            domain = 'https://' + domain
        detail_url = '{}{}'.format(domain, rfc.get_absolute_url())

        # Send an email to the requester.
        subject = 'Change request {} has been approved at CAB'.format(rfc.pk)
        text_content = """This is an automated message to let you know that change request
            {} ("{}") has been approved at CAB, and it may now be undertaken as planned.\n
            {}\n
            """.format(rfc.pk, rfc.title, detail_url)
        html_content = """<p>This is an automated message to let you know that change request
            {0} ("{1}") has been approved at CAB, and it may now be undertaken as planned.</p>
            <ul><li><a href="{2}">{2}</a></li></ul>
            """.format(rfc.pk, rfc.title, detail_url)
        msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, [rfc.requester.email])
        msg.attach_alternative(html_content, 'text/html')
        msg.send()

        return HttpResponseRedirect(rfc.get_absolute_url())


class ChangeRequestExport(LoginRequiredMixin, View):
    """A custom view to export all ChangeRequest objects to an Excel spreadsheet.
    """
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=change_requests_{}_{}.xlsx'.format(date.today().isoformat(), datetime.now().strftime('%H%M'))
        rfcs = ChangeRequest.objects.all()
        response = change_request_export(response, rfcs)
        return response


class ChangeRequestCalendar(LoginRequiredMixin, ListView):
    model = ChangeRequest
    template_name = 'registers/changerequest_calendar.html'

    def get_date_param(self, **kwargs):
        if 'date' in self.kwargs:
            # Parse the date YYYY-MM-DD, then YYYY-MM.
            if re.match('^\d{4}-\d{1,2}-\d{1,2}$', self.kwargs['date']):
                return ('week', datetime.strptime(self.kwargs['date'], '%Y-%m-%d').date())
            elif re.match('^\d{4}-\d{1,2}$', self.kwargs['date']):
                return ('month', datetime.strptime(self.kwargs['date'], '%Y-%m').date())
        else:
            # If no starting date is specifed, fall back to Monday in the current week.
            return ('week', date.today() - timedelta(days=date.today().weekday()))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_title'] = 'DBCA Office of Information Management'
        context['site_acronym'] = 'OIM'
        cal, d = self.get_date_param()
        context['start'] = d
        context['today'] = date.today()
        if cal == 'week':
            context['format'] = 'Weekly'
            context['date_last'] = d - timedelta(7)
            context['date_next'] = d + timedelta(7)
        elif cal == 'month':
            context['format'] = 'Monthly'
            context['date_last'] = (d + relativedelta(months=-1)).strftime('%Y-%m')
            context['date_next'] = (d + relativedelta(months=1)).strftime('%Y-%m')
        # Breadcrumb links:
        links = [
            (reverse("change_request_list"), "Change request register"),
            (None, "Calendar")
        ]
        context["breadcrumb_trail"] = breadcrumbs_list(links)
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        cal, d = self.get_date_param()
        if cal == 'week':
            # Convert week_start to a TZ-aware datetime object.
            week_start = datetime.combine(d, datetime.min.time()).astimezone(TZ)
            week_end = week_start + timedelta(days=7)
            return queryset.filter(planned_start__range=[week_start, week_end]).order_by('planned_start')
        elif cal == 'month':
            # Convert month_start to a TZ-aware datetime object.
            month_start = datetime.combine(d, datetime.min.time()).astimezone(TZ)
            last_day = monthrange(d.year, d.month)[1]
            month_end = datetime.combine(date(d.year, d.month, last_day), datetime.max.time()).astimezone(TZ)
            return queryset.filter(planned_start__range=[month_start, month_end]).order_by('planned_start')
        return queryset


class ChangeRequestComplete(LoginRequiredMixin, UpdateView):
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
        if self.request.user.email.lower() not in [rfc.requester.email.lower(), rfc.implementer.email.lower()]:
            messages.warning(self.request, 'You are not authorised to complete change request {}.'.format(rfc.pk))
            return HttpResponseRedirect(rfc.get_absolute_url())
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_title'] = 'DBCA Office of Information Management'
        context['site_acronym'] = 'OIM'
        rfc = self.get_object()
        context['page_title'] = 'Complete/finalise change request {}'.format(rfc.pk)
        # Breadcrumb links:
        links = [
            (reverse("change_request_list"), "Change request register"),
            (reverse("change_request_detail", args=(rfc.pk,)), rfc.pk),
            (None, "Complete")
        ]
        context['breadcrumb_trail'] = breadcrumbs_list(links)
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
            messages.success(self.request, 'Change request {} has been marked as completed.'.format(rfc.pk))
        elif d['outcome'] == 'rollback':
            rfc.status = 5
            log.log = 'Change {} was marked "Undertaken and rolled back" by {}.'.format(rfc.pk, self.request.user.get_full_name())
            messages.info(self.request, 'Change request {} has been marked as rolled back.'.format(rfc.pk))
        elif d['outcome'] == 'cancelled':
            rfc.status = 6
            log.log = 'Change {} was marked "Cancelled" by {}.'.format(rfc.pk, self.request.user.get_full_name())
            messages.info(self.request, 'Change request {} has been marked as cancelled.'.format(rfc.pk))
        rfc.save()
        log.save()

        return super().form_valid(form)


class RiskAssessmentITSystemList(LoginRequiredMixin, ListView):
    """A list view to display a summary of risk assessments for all IT Systems.
    """
    model = ITSystem
    paginate_by = 20
    template_name = 'registers/riskassessment_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_title'] = 'DBCA Office of Information Management'
        context['site_acronym'] = 'OIM'
        context['page_title'] = 'Risk Assessment - IT Systems'
        if 'q' in self.request.GET:
            context['query_string'] = self.request.GET['q']
        context['risk_categories'] = [i[0] for i in RISK_CATEGORY_CHOICES]
        # Breadcrumb links:
        links = [(None, 'Risk assessments')]
        context["breadcrumb_trail"] = breadcrumbs_list(links)
        return context

    def get_queryset(self):
        qs = super().get_queryset()
        # Default to prod/prod-legacy IT systems only.
        qs = qs.filter(**ITSystem.ACTIVE_FILTER).order_by('system_id')
        # Did we pass in a search string? If so, filter the queryset and return it.
        if 'q' in self.request.GET and self.request.GET['q']:
            from .admin import ITSystemAdmin
            q = search_filter(ITSystemAdmin.search_fields, self.request.GET['q'])
            qs = qs.filter(q).distinct()
        return qs


class RiskAssessmentITSystemDetail(LoginRequiredMixin, DetailView):
    """A detail view to display a risk assessments and dependencies for a single IT System.
    """
    model = ITSystem
    template_name = 'registers/riskassessment_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context['site_title'] = 'DBCA Office of Information Management'
        context['site_acronym'] = 'OIM'
        context['page_title'] = 'Risk Assessment - {}'.format(obj)
        context['obj_dependencies'] = obj.dependencies.order_by('category')
        context['itsystem_ct'] = ContentType.objects.get_for_model(obj)
        context['dependency_ct'] = ContentType.objects.get(app_label='bigpicture', model='dependency')
        context['risk_categories'] = [i[0] for i in RISK_CATEGORY_CHOICES]
        if obj.extra_data and 'signal_science_tags' in obj.extra_data:
            context['sig_sci_tags'] = obj.extra_data['signal_science_tags']
        else:
            context['sig_sci_tags'] = None
        # Breadcrumb links:
        links = [(reverse("riskassessment_itsystem_list"), "Risk assessments"), (None, obj.system_id)]
        context["breadcrumb_trail"] = breadcrumbs_list(links)
        return context


class RiskAssessmentGlossary(LoginRequiredMixin, TemplateView):
    """A static template to display a glossary of what each risk assessment means, per category.
    """
    template_name = 'registers/riskassessment_glossary.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_title'] = 'DBCA Office of Information Management'
        context['site_acronym'] = 'OIM'
        context["page_title"] = "Glossary"
        # Breadcrumb links:
        links = [(reverse("riskassessment_itsystem_list"), "Risk assessments"), (None, "Glossary")]
        context["breadcrumb_trail"] = breadcrumbs_list(links)
        return context


class RiskAssessmentExport(LoginRequiredMixin, View):
    """A custom view to export IT System risk assessments to an Excel spreadsheet.
    """
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=risk_assessments_it_systems_{}_{}.xlsx'.format(
            date.today().isoformat(), datetime.now().strftime('%H%M')
        )
        it_systems = ITSystem.objects.filter(**ITSystem.ACTIVE_FILTER).order_by('system_id')
        response = riskassessment_export(response, it_systems)
        return response


class SignalScienceTags(LoginRequiredMixin, TemplateView):
    """A static template to display a glossary of what each risk assessment means, per category.
    """
    template_name = 'registers/signal_science_tags.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_title'] = 'DBCA Office of Information Management'
        context['site_acronym'] = 'OIM'
        context["page_title"] = "Signal Science system tags"
        # Breadcrumb links:
        links = [(reverse("riskassessment_itsystem_list"), "Risk assessments"), (None, "Signal Science tags")]
        context["breadcrumb_trail"] = breadcrumbs_list(links)
        tags = {}
        for it in ITSystem.objects.all():
            if it.extra_data and 'signal_science_tags' in it.extra_data:
                for tag_type, count in it.extra_data['signal_science_tags'].items():
                    if tag_type not in tags:
                        tags[tag_type] = []
                    tags[tag_type].append((count, it.name, reverse("riskassessment_itsystem_detail", args=(it.pk,))))
        for val in tags.values():
            val.sort(reverse=True)
        tags_top5 = {}
        for k, v in tags.items():
            tags_top5[k] = v[0:5]
        context['tags'] = tags_top5
        return context
