from copy import copy
from django import forms
from django.conf.urls import url
from django.contrib.admin import register, ModelAdmin, StackedInline
from django.contrib.auth.models import Group, User
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.safestring import mark_safe
from io import BytesIO
from reversion.admin import VersionAdmin
import unicodecsv as csv

from .models import (
    UserGroup, ITSystemHardware, Platform, ITSystem, ITSystemDependency, Backup, BusinessService,
    BusinessFunction, BusinessProcess, ProcessITSystemRelationship, Incident, IncidentLog)
from .utils import smart_truncate


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
        urls = [
            url(r'^export/$',
                self.admin_site.admin_view(self.export),
                name='itsystemhardware_export'),
        ] + urls
        return urls

    def export(self, request):
        """Exports ITSystemHardware data to a CSV. NOTE: report output excludes objects
        that are marked as decommissioned.
        """
        # Define fields to output.
        fields = [
            'hostname', 'host', 'os_name', 'role', 'production', 'instance_id', 'patch_group', 'itsystem_system_id',
            'itsystem_name', 'itsystem_cost_centre', 'itsystem_availability', 'itsystem_custodian',
            'itsystem_owner', 'it_system_data_custodian']

        # Write data for ITSystemHardware objects to the CSV.
        stream = BytesIO()
        wr = csv.writer(stream, encoding='utf-8')
        wr.writerow(fields)  # CSV header row.
        for i in ITSystemHardware.objects.filter(decommissioned=False):
            if i.computer.ec2_instance:
                ec2 = i.computer.ec2_instance.ec2id
            else:
                ec2 = ''
            if i.itsystem_set.all().exclude(status=3).exists():
                # Write a row for each linked, non-decommissioned ITSystem.
                for it in i.itsystem_set.all().exclude(status=3):
                    wr.writerow([
                        i.computer.hostname, i.host, i.computer.os_name, i.get_role_display(),
                        i.production, ec2, i.patch_group, it.system_id, it.name, it.cost_centre,
                        it.get_availability_display(), it.custodian, it.owner, it.data_custodian])
            else:
                # No IT Systems - just record the hardware details.
                wr.writerow([
                    i.computer.hostname, i.host, i.computer.os_name, i.get_role_display(), i.production,
                    ec2, i.patch_group])

        response = HttpResponse(stream.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=itsystemhardware_export.csv'
        return response


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
        """Validation on the biller_code field: must be unique (ignore null values).
        """
        data = self.cleaned_data['biller_code']
        if data and ITSystem.objects.filter(biller_code=data).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('An IT System with this biller code already exists.')
        return data


@register(ITSystem)
class ITSystemAdmin(VersionAdmin):
    filter_horizontal = ('platforms', 'hardwares', 'user_groups')
    list_display = (
        'system_id', 'name', 'acronym', 'status', 'cost_centre', 'owner', 'custodian',
        'preferred_contact', 'access', 'authentication')
    list_filter = (
        'access', 'authentication', 'status', 'contingency_plan_status',
        'system_type', 'platforms', 'oim_internal_only')
    search_fields = (
        'system_id', 'owner__username', 'owner__email', 'name', 'acronym', 'description',
        'custodian__username', 'custodian__email', 'link', 'documentation', 'cost_centre__code')
    raw_id_fields = (
        'owner', 'custodian', 'data_custodian', 'preferred_contact', 'cost_centre',
        'bh_support', 'ah_support')
    readonly_fields = ('extra_data_pretty', 'description_html')
    fields = [
        ('system_id', 'acronym'),
        ('name', 'status'),
        'link',
        ('cost_centre', 'owner'),
        ('custodian', 'data_custodian'),
        'preferred_contact',
        ('bh_support', 'ah_support'),
        'platforms',
        'documentation',
        'technical_documentation',
        'status_html',
        ('authentication', 'access'),
        'description',
        'notes',
        ('criticality', 'availability'),
        'schema_url',
        'hardwares',
        'user_groups',
        'system_reqs',
        ('system_type', 'oim_internal_only'),
        'request_access',
        ('vulnerability_docs', 'recovery_docs'),
        'workaround',
        ('mtd', 'rto', 'rpo'),
        ('contingency_plan', 'contingency_plan_status'),
        'contingency_plan_last_tested',
        'system_health',
        'system_creation_date',
        'backup_info',
        'risks',
        'sla',
        'critical_period',
        'alt_processing',
        'technical_recov',
        'post_recovery',
        'variation_iscp',
        'user_notification',
        'other_projects',
        'function',
        'use',
        'capability',
        'unique_evidence',
        'point_of_truth',
        'legal_need_to_retain',
        'biller_code',
        'extra_data',
    ]
    # Override the default reversion/change_list.html template:
    change_list_template = 'admin/registers/itsystem/change_list.html'
    form = ITSystemForm  # Use the custom ModelForm.

    def get_urls(self):
        urls = super(ITSystemAdmin, self).get_urls()
        urls = [
            # Note that we don't wrap the view below in AdminSite.admin_view()
            # on purpose, as we want it generally accessible.
            url(r'^export/$', self.export, name='itsystem_export'),
        ] + urls
        return urls

    def export(self, request):
        """Exports ITSystem data to a CSV.
        """
        # Define model fields to output.
        fields = [
            'system_id', 'name', 'acronym', 'status_display', 'description',
            'criticality_display', 'availability_display', 'system_type_display',
            'cost_centre', 'division_name', 'owner', 'custodian', 'data_custodian', 'preferred_contact',
            'link', 'documentation', 'technical_documentation', 'authentication_display',
            'access_display', 'request_access', 'status_html', 'schema_url',
            'bh_support', 'ah_support', 'system_reqs', 'vulnerability_docs',
            'workaround', 'recovery_docs', 'date_updated']
        header = copy(fields)  # We also output non-field values.
        header.append('associated_hardware')

        # Write data for ITSystem objects to the CSV:
        stream = BytesIO()
        wr = csv.writer(stream, encoding='utf-8')
        wr.writerow(header)  # CSV header.
        for i in ITSystem.objects.all().order_by(
                'system_id').exclude(status=3):  # Exclude decommissioned
            row = [getattr(i, f) for f in fields]
            row.append(', '.join(i.hardwares.filter(decommissioned=False).values_list('computer__hostname', flat=True)))
            wr.writerow(row)

        response = HttpResponse(stream.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=itsystem_export.csv'
        return response


@register(ITSystemDependency)
class ITSystemDependencyAdmin(VersionAdmin):
    list_display = ('itsystem', 'dependency', 'criticality')
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

    def itsystem_dependency_reports(self, request):
        context = {'title': 'IT System dependency reports'}
        return TemplateResponse(
            request, 'admin/itsystemdependency_reports.html', context)

    def itsystem_dependency_report_all(self, request):
        """Returns a CSV containing all recorded dependencies.
        """
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
        """Returns a CSV containing all systems without dependencies recorded.
        """
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


@register(Backup)
class BackupAdmin(VersionAdmin):
    raw_id_fields = ('computer',)
    list_display = (
        'computer', 'operating_system', 'role', 'status', 'last_tested')
    list_editable = ('operating_system', 'role', 'status', 'last_tested')
    search_fields = ('computer__hostname',)
    list_filter = ('role', 'status', 'operating_system')
    date_hierarchy = 'last_tested'


@register(BusinessService)
class BusinessServiceAdmin(VersionAdmin):
    list_display = ('number', 'name')
    search_fields = ('name', 'description')


@register(BusinessFunction)
class BusinessFunctionAdmin(VersionAdmin):
    list_display = ('name', 'function_services')
    list_filter = ('services',)
    search_fields = ('name', 'description')

    def function_services(self, obj):
        return ', '.join([str(i.number) for i in obj.services.all()])
    function_services.short_description = 'services'


@register(BusinessProcess)
class BusinessProcessAdmin(VersionAdmin):
    list_display = ('name', 'criticality')
    list_filter = ('criticality', 'functions')
    search_fields = ('name', 'description', 'functions__name')


@register(ProcessITSystemRelationship)
class ProcessITSystemRelationshipAdmin(VersionAdmin):
    list_display = ('process', 'itsystem', 'importance')
    list_filter = ('importance', 'process', 'itsystem')
    search_fields = ('process__name', 'itsystem__name')


class IncidentLogInline(StackedInline):
    model = IncidentLog
    extra = 0


@register(Incident)
class IncidentAdmin(ModelAdmin):
    date_hierarchy = 'start'
    filter_horizontal = ('it_systems', 'locations', 'platforms')
    list_display = (
        'id', 'created', 'description_trunc', 'priority', 'start', 'resolution', 'manager', 'owner')
    inlines = [IncidentLogInline]
    list_filter = ('priority', 'detection', 'category')
    search_fields = (
        'description', 'it_systems__name', 'locations__name', 'platform__name', 'manager__email',
        'owner__email')

    def description_trunc(self, obj):
        return smart_truncate(obj.description)
    description_trunc.short_description = 'description'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        oim = Group.objects.get_or_create(name='OIM Staff')[0]
        if db_field.name in ['manager', 'owner']:
            kwargs['queryset'] = User.objects.filter(groups__in=[oim], is_active=True, is_staff=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
