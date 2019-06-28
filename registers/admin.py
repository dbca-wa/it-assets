from datetime import datetime
from django import forms
from django.conf import settings
from django.conf.urls import url
from django.contrib import messages
from django.contrib.admin import register, ModelAdmin, StackedInline, SimpleListFilter
from django.contrib.auth.models import Group, User
from django.core.mail import EmailMultiAlternatives
from django.forms import ModelChoiceField, ModelForm
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.safestring import mark_safe
from io import BytesIO
from pytz import timezone
from reversion.admin import VersionAdmin
import unicodecsv as csv

from .models import (
    UserGroup, ITSystemHardware, Platform, ITSystem, ITSystemDependency,
    Incident, IncidentLog, StandardChange, ChangeRequest, ChangeLog)
from .utils import smart_truncate
from .views import ITSystemExport, ITSystemDiscrepancyReport, ITSystemHardwareExport, IncidentExport, ChangeRequestExport


@register(UserGroup)
class UserGroupAdmin(VersionAdmin):
    list_display = ('name', 'user_count')
    search_fields = ('name',)


@register(ITSystemHardware)
class ITSystemHardwareAdmin(VersionAdmin):
    list_display = ('computer', 'role', 'affected_itsystems', 'production', 'decommissioned', 'patch_group', 'host')
    list_filter = ('role', 'production', 'decommissioned', 'patch_group', 'host')
    raw_id_fields = ('computer',)
    search_fields = ('computer__hostname', 'computer__sam_account_name', 'description', 'host')
    # Override the default reversion/change_list.html template:
    change_list_template = 'admin/registers/itsystemhardware/change_list.html'

    def affected_itsystems(self, obj):
        # Exclude decommissioned systems from the count.
        count = obj.itsystem_set.count()
        url = reverse('admin:registers_itsystem_changelist')
        return mark_safe('<a href="{}?hardwares__in={}">{}</a>'.format(url, obj.pk, count))
    affected_itsystems.short_description = 'IT Systems'

    def get_urls(self):
        urls = super(ITSystemHardwareAdmin, self).get_urls()
        urls = [path('export/', self.admin_site.admin_view(ITSystemHardwareExport.as_view()), name='itsystemhardware_export')] + urls
        return urls


@register(Platform)
class PlatformAdmin(VersionAdmin):
    list_display = ('name', 'category', 'affected_itsystems')
    list_filter = ('category',)
    search_fields = ('name',)

    def affected_itsystems(self, obj):
        # Exclude decommissioned systems from the count.
        count = obj.itsystem_set.all().exclude(status=3).count()
        url = reverse('admin:registers_itsystem_changelist')
        return mark_safe('<a href="{}?platforms__in={}">{}</a>'.format(url, obj.pk, count))
    affected_itsystems.short_description = 'IT Systems'


class ITSystemForm(forms.ModelForm):
    class Meta:
        model = ITSystem
        exclude = []

    def clean_biller_code(self):
        # Validation on the biller_code field - must be unique (ignore null values).
        data = self.cleaned_data['biller_code']
        if data and ITSystem.objects.filter(biller_code=data).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('An IT System with this biller code already exists.')
        return data


@register(ITSystem)
class ITSystemAdmin(VersionAdmin):
    filter_horizontal = ('platforms', 'hardwares', 'user_groups')
    list_display = (
        'system_id', 'name', 'status', 'cost_centre', 'owner', 'technology_custodian', 'bh_support')
    list_filter = (
        'status', 'system_type', 'availability', 'seasonality', 'recovery_category')
    search_fields = (
        'system_id', 'owner__username', 'owner__email', 'name', 'acronym', 'description',
        'technology_custodian__username', 'technology_custodian__email', 'link', 'documentation', 'cost_centre__code')
    raw_id_fields = (
        'owner', 'technology_custodian', 'information_custodian', 'cost_centre', 'bh_support', 'ah_support')
    fieldsets = (
        ('Overview', {
            'fields': (
                'system_id',
                ('name', 'acronym'),
                ('link', 'status'),
                ('owner', 'cost_centre'),
                ('technology_custodian', 'information_custodian'),
                ('bh_support', 'ah_support'),
                ('availability', 'seasonality'),
                'description',
                'system_type',
            )
        }),
        ('Technical information', {
            'fields': (
                ('backups', 'recovery_category'),
                ('emergency_operations', 'online_bookings', 'visitor_safety'),
                'user_notification',
                'documentation',
                'technical_documentation',
                'status_url',
                'user_groups',
                'application_server',
                'database_server',
                'network_storage',
                'system_reqs',
                'platforms',
                'hardwares',
                'oim_internal_only',
                ('authentication', 'access'),
                'biller_code',
            )
        }),
        ('Retention and disposal', {
            'fields': (
                'defunct_date',
                'retention_reference_no',
                'disposal_action',
                'custody',
                'retention_comments',
            )
        }),
    )
    # Override the default reversion/change_list.html template:
    change_list_template = 'admin/registers/itsystem/change_list.html'
    form = ITSystemForm  # Use the custom ModelForm.
    save_on_top = True

    def get_urls(self):
        urls = super(ITSystemAdmin, self).get_urls()
        urls = [
            path('export/', self.admin_site.admin_view(ITSystemExport.as_view()), name='itsystem_export'),
            path('discrepancies/', self.admin_site.admin_view(ITSystemDiscrepancyReport.as_view()), name='itsystem_discrepancies'),
        ] + urls
        return urls


@register(ITSystemDependency)
class ITSystemDependencyAdmin(VersionAdmin):
    list_display = ('itsystem', 'itsystem_status', 'dependency', 'criticality')
    list_filter = ('criticality',)
    search_fields = ('itsystem__name', 'dependency__name', 'description')
    # Override the default reversion/change_list.html template:
    change_list_template = 'admin/registers/itsystemdependency/change_list.html'

    def get_urls(self):
        urls = super(ITSystemDependencyAdmin, self).get_urls()
        extra_urls = [
            url(
                r'^reports/$',
                self.admin_site.admin_view(self.itsystem_dependency_reports),
                name='itsystem_dependency_reports'
            ),
            url(
                r'^reports/all/$',
                self.admin_site.admin_view(self.itsystem_dependency_report_all),
                name='itsystem_dependency_report_all'
            ),
            url(
                r'^reports/no-deps/$',
                self.admin_site.admin_view(self.itsystem_dependency_report_nodeps),
                name='itsystem_dependency_report_nodeps'
            ),
        ]
        return extra_urls + urls

    def itsystem_status(self, obj):
        return obj.itsystem.get_status_display()
    itsystem_status.short_description = 'IT system status'

    def itsystem_dependency_reports(self, request):
        context = {'title': 'IT System dependency reports'}
        return TemplateResponse(
            request, 'admin/itsystemdependency_reports.html', context)

    def itsystem_dependency_report_all(self, request):
        # Returns a CSV containing all recorded dependencies.
        fields = [
            'IT System', 'System status', 'Dependency', 'Dependency status',
            'Criticality', 'Description']

        # Write data for ITSystemHardware objects to the CSV.
        stream = BytesIO()
        wr = csv.writer(stream, encoding='utf-8')
        wr.writerow(fields)  # CSV header row.
        for i in ITSystemDependency.objects.all():
            wr.writerow([
                i.itsystem.name, i.itsystem.get_status_display(),
                i.dependency.name, i.dependency.get_status_display(),
                i.get_criticality_display(), i.description])

        response = HttpResponse(stream.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=itsystemdependency_all.csv'
        return response

    def itsystem_dependency_report_nodeps(self, request):
        # Returns a CSV containing all systems without dependencies recorded.
        fields = ['IT System', 'System status']

        # Write data for ITSystemHardware objects to the CSV.
        stream = BytesIO()
        wr = csv.writer(stream, encoding='utf-8')
        wr.writerow(fields)  # CSV header row.
        deps = ITSystemDependency.objects.all().values_list('pk')
        for i in ITSystem.objects.all().exclude(pk__in=deps):
            wr.writerow([i.name, i.get_status_display()])

        response = HttpResponse(stream.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=itsystem_no_deps.csv'
        return response


class IncidentLogInline(StackedInline):
    model = IncidentLog
    extra = 0


class UserModelChoiceField(ModelChoiceField):
    """A lightly-customised choice field for users (displays user full name).
    """
    def label_from_instance(self, obj):
        # Return a string of the format: "firstname lastname (username)"
        return "{} ({})".format(obj.get_full_name(), obj.username)


class IncidentAdminForm(ModelForm):
    """A lightly-customised ModelForm for Incidents, to use the UserModelChoiceField widget.
    """
    owner = UserModelChoiceField(queryset=None, required=False, help_text='Incident owner')
    manager = UserModelChoiceField(queryset=None, required=False, help_text='Incident manager')

    def __init__(self, *args, **kwargs):
        super(IncidentAdminForm, self).__init__(*args, **kwargs)
        # Set the user choice querysets on __init__ in order that the project still works with an empty database.
        self.fields['owner'].queryset = User.objects.filter(
            groups__in=[Group.objects.get(name='OIM Staff')], is_active=True, is_staff=True).order_by('first_name')
        self.fields['manager'].queryset = User.objects.filter(
            groups__in=[Group.objects.get(name='IT Coordinators')], is_active=True, is_staff=True).order_by('first_name')

    class Meta:
        model = Incident
        exclude = []


class IncidentStatusListFilter(SimpleListFilter):
    """A custom list filter to restrict displayed incidents to ongoing/resolved status.
    """
    title = 'status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return (
            ('Ongoing', 'Ongoing'),
            ('Resolved', 'Resolved')
        )

    def queryset(self, request, queryset):
        if self.value() == 'Ongoing':
            return queryset.filter(resolution__isnull=True)
        if self.value() == 'Resolved':
            return queryset.filter(resolution__isnull=False)


@register(Incident)
class IncidentAdmin(ModelAdmin):
    form = IncidentAdminForm
    date_hierarchy = 'start'
    filter_horizontal = ('it_systems', 'locations')
    inlines = [IncidentLogInline]
    list_display = (
        'id', 'created', 'description_trunc', 'priority', 'start', 'resolution', 'manager_name',
        'owner_name')
    list_filter = (IncidentStatusListFilter, 'priority', 'detection', 'category')
    list_select_related = ('manager', 'owner')
    search_fields = (
        'id', 'description', 'it_systems__name', 'locations__name', 'manager__email', 'owner__email',
        'url', 'workaround', 'root_cause', 'remediation')
    change_list_template = 'admin/registers/incident/change_list.html'

    def manager_name(self, obj):
        if obj.manager:
            return obj.manager.get_full_name()
        return ''
    manager_name.short_description = 'manager'

    def owner_name(self, obj):
        if obj.owner:
            return obj.owner.get_full_name()
        return ''
    owner_name.short_description = 'owner'

    def description_trunc(self, obj):
        return smart_truncate(obj.description)
    description_trunc.short_description = 'description'

    def get_urls(self):
        urls = super(IncidentAdmin, self).get_urls()
        urls = [path('export/', self.admin_site.admin_view(IncidentExport.as_view()), name='incident_export')] + urls
        return urls

    def it_systems_affected(self, obj):
        return ', '.join([i.name for i in obj.it_systems.all()])
    it_systems_affected.short_description = 'IT Systems'

    def locations_affected(self, obj):
        return ', '.join([i.name for i in obj.locations.all()])
    locations_affected.short_description = 'locations'


@register(StandardChange)
class StandardChangeAdmin(ModelAdmin):
    date_hierarchy = 'created'
    filter_horizontal = ('it_systems',)
    list_display = ('id', 'name', 'endorser', 'expiry')
    raw_id_fields = ('endorser',)
    search_fields = ('id', 'name', 'endorser__email')


class ChangeLogInline(StackedInline):
    model = ChangeLog
    extra = 0
    fields = ('created', 'log')
    readonly_fields = ('created',)


class CompletionListFilter(SimpleListFilter):
    """A custom list filter to restrict displayed RFCs by completion status.
    """
    title = 'completion'
    parameter_name = 'completion'

    def lookups(self, request, model_admin):
        return (
            ('Complete', 'Complete'),
            ('Incomplete', 'Incomplete')
        )

    def queryset(self, request, queryset):
        if self.value() == 'Complete':
            return queryset.filter(completed__isnull=False)
        if self.value() == 'Incomplete':
            return queryset.filter(completed__isnull=True)


def email_endorser(modeladmin, request, queryset):
    """A custom admin action to (re)send an email to the endorser, requesting that they endorse an RFC.
    """
    for rfc in queryset:
        if rfc.is_submitted:
            rfc.email_endorser()
            msg = 'Request for approval emailed to {}.'.format(rfc.endorser.get_full_name())
            log = ChangeLog(change_request=rfc, log=msg)
            log.save()
            messages.success(request, msg)

email_endorser.short_description = 'Send email to the endorser requesting endorsement of a change'


def email_implementer(modeladmin, request, queryset):
    """A custom admin action to (re)send email to the implementer requesting that they record completion.
    """
    for rfc in queryset:
        if rfc.status == 3 and rfc.planned_end <= datetime.now().astimezone(timezone(settings.TIME_ZONE)) and rfc.completed is None:
            rfc.email_implementer()
            msg = 'Request for completion record-keeping emailed to {}.'.format(rfc.implementer.get_full_name())
            log = ChangeLog(change_request=rfc, log=msg)
            log.save()
            messages.success(request, msg)

email_implementer.short_description = 'Send email to the implementer to record completion of a finished change'


def cab_approve(modeladmin, request, queryset):
    """A custom admin action to bulk-approve RFCs at CAB.
    """
    for rfc in queryset:
        if rfc.is_scheduled:
            # Set the RFC status and record a log.
            rfc.status = 3
            rfc.save()
            msg = 'Change request {} has been approved at CAB; it may now be carried out as planned.'.format(rfc.pk)
            log = ChangeLog(change_request=rfc, log=msg)
            log.save()
            # Send an email to the requester.
            subject = 'Change request {} has been approved at CAB'.format(rfc.pk)
            detail_url = request.build_absolute_uri(rfc.get_absolute_url())
            text_content = """This is an automated message to let you know that change request
                {} ("{}") has been approved at CAB and may now be carried out as planned.\n
                Following completion, rollback or cancellation, please visit the following URL
                and record the outcome of the change:\n
                {}\n
                """.format(rfc.pk, rfc.title, detail_url)
            html_content = """<p>This is an automated message to let you know that change request
                {0} ("{1}") has been approved at CAB and may now be carried out as planned.</p>
                <p>Following completion, rollback or cancellation, please visit the following URL
                and record the outcome of the change:</p>
                <ul><li><a href="{2}">{2}</a></li></ul>
                """.format(rfc.pk, rfc.title, detail_url)
            msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, [rfc.requester.email])
            msg.attach_alternative(html_content, 'text/html')
            msg.send()
            # Success notification.
            msg = 'RFC {} status set to "Ready"; requester has been emailed.'.format(rfc.pk)
            messages.success(request, msg)

cab_approve.short_description = 'Mark selected change requests as approved at CAB'


def cab_reject(modeladmin, request, queryset):
    """A custom admin action to reject RFCs at CAB.
    """
    for rfc in queryset:
        if rfc.is_scheduled:
            # Set the RFC status and record a log.
            rfc.status = 0
            rfc.save()
            msg = 'Change request {} has been rejected at CAB; status has been reset to Draft.'.format(rfc.pk)
            log = ChangeLog(change_request=rfc, log=msg)
            log.save()
            # Send an email to the requester.
            subject = 'Change request {} has been rejected at CAB'.format(rfc.pk)
            detail_url = request.build_absolute_uri(rfc.get_absolute_url())
            text_content = """This is an automated message to let you know that change request
                {} ("{}") has been rejected at CAB, and its status reset to draft.\n
                Please review any log messages recorded on the change request as context prior
                to making any required alterations and re-submission:\n
                {}\n
                """.format(rfc.pk, rfc.title, detail_url)
            html_content = """<p>This is an automated message to let you know that change request
                {0} ("{1}") has been rejected at CAB, and its status reset to draft.</p>
                <p>Please review any log messages recorded on the change request as context prior
                to making any required alterations and re-submission:</p>
                <ul><li><a href="{2}">{2}</a></li></ul>
                """.format(rfc.pk, rfc.title, detail_url)
            msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, [rfc.requester.email])
            msg.attach_alternative(html_content, 'text/html')
            msg.send()
            # Success notification.
            msg = 'RFC {} status set to "Draft"; requester has been emailed.'.format(rfc.pk)
            messages.success(request, msg)

cab_reject.short_description = 'Mark selected change requests as rejected at CAB (set to draft status)'


@register(ChangeRequest)
class ChangeRequestAdmin(ModelAdmin):
    actions = [cab_approve, cab_reject, email_endorser, email_implementer]
    change_list_template = 'admin/registers/changerequest/change_list.html'
    date_hierarchy = 'planned_start'
    filter_horizontal = ('it_systems',)
    inlines = [ChangeLogInline]
    list_display = (
        'id', 'title', 'change_type', 'requester_name', 'endorser_name', 'implementer_name', 'status',
        'created', 'planned_start', 'planned_end', 'completed')
    list_filter = ('change_type', 'status', CompletionListFilter)
    raw_id_fields = ('requester', 'endorser', 'implementer')
    search_fields = (
        'id', 'title', 'requester__email', 'endorser__email', 'implementer__email', 'implementation',
        'communication', 'reference_url')

    def requester_name(self, obj):
        if obj.requester:
            return obj.requester.get_full_name()
        return ''
    requester_name.short_description = 'requester'

    def endorser_name(self, obj):
        if obj.endorser:
            return obj.endorser.get_full_name()
        return ''
    endorser_name.short_description = 'endorser'

    def implementer_name(self, obj):
        if obj.implementer:
            return obj.implementer.get_full_name()
        return ''
    implementer_name.short_description = 'implementer'

    def get_urls(self):
        urls = super(ChangeRequestAdmin, self).get_urls()
        urls = [path('export/', self.admin_site.admin_view(ChangeRequestExport.as_view()), name='changerequest_export')] + urls
        return urls
