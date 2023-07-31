from django import forms
from django.contrib import admin
from django.urls import path
from django.utils.html import mark_safe
import json

from itassets.utils import ModelDescMixin
from .models import DepartmentUser, Location, CostCentre, AscenderActionLog
from .views import DepartmentUserExport
from .utils import title_except


class DepartmentUserForm(forms.ModelForm):

    class Meta:
        model = DepartmentUser
        exclude = []

    def clean_ad_guid(self):
        return self.cleaned_data['ad_guid'] or None

    def clean_employee_id(self):
        if self.cleaned_data['employee_id'] == '':
            return None
        else:
            return self.cleaned_data['employee_id']


@admin.register(DepartmentUser)
class DepartmentUserAdmin(ModelDescMixin, admin.ModelAdmin):

    class AssignedLicenceFilter(admin.SimpleListFilter):
        title = 'assigned licences'
        parameter_name = 'assigned_licences'

        def lookups(self, request, model_admin):
            return (
                ('MICROSOFT 365 E5', 'Microsoft 365 E5 (On-premise)'),
                ('MICROSOFT 365 F3', 'Microsoft 365 F3 (Cloud)'),
                ('NONE', 'No licence')
            )

        def queryset(self, request, queryset):
            if self.value():
                if self.value() == "NONE":
                    return queryset.filter(assigned_licences=[])
                else:
                    return queryset.filter(assigned_licences__contains=[self.value()])

    change_list_template = 'admin/organisation/departmentuser/change_list.html'
    form = DepartmentUserForm
    list_display = (
        'email', 'name', 'title', 'employee_id', 'active', 'cost_centre', 'division', 'unit', 'm365_licence', 'account_type',
    )
    list_filter = (AssignedLicenceFilter, 'active', 'account_type', 'shared_account')
    model_description = DepartmentUser.__doc__
    search_fields = ('name', 'email', 'title', 'employee_id', 'ad_guid', 'azure_guid')
    raw_id_fields = ('manager',)
    readonly_fields = (
        'active', 'email', 'name', 'given_name', 'surname', 'azure_guid', 'ad_guid', 'ascender_full_name', 'ascender_preferred_name',
        'assigned_licences', 'proxy_addresses', 'dir_sync_enabled', 'ascender_org_path', 'geo_location_desc',
        'paypoint', 'employment_status', 'position_title', 'position_number', 'job_start_date', 'job_end_date', 'ascender_data_updated',
        'manager_name', 'extended_leave', 'employee_id',
    )
    fieldsets = (
        ('Ascender account information', {
            'description': '''<span class="errornote">These data are specific to the Ascender HR database. Data is these fields is maintained in Ascender.</span>''',
            'fields': (
                'employee_id',
                'ascender_full_name',
                'ascender_preferred_name',
                'ascender_org_path',
                'position_title',
                'position_number',
                'geo_location_desc',
                'paypoint',
                'employment_status',
                'manager_name',
                'job_start_date',
                'job_end_date',
                'extended_leave',
                'ascender_data_updated',
            ),
        }),
        ('Microsoft 365 and Active Directory account information', {
            'description': '<span class="errornote">Data in these fields is maintained in Azure Active Directory.</span>',
            'fields': (
                'active',
                'email',
                'name',
                'assigned_licences',
                'dir_sync_enabled',
                'azure_guid',
                'ad_guid',
            ),
        }),
        ('User information fields', {
            'description': '''<span class="errornote">Data in these fields can be edited here for display in the Address Book.<br>
                Do not edit information in this section without a service request from an authorised person.</span>''',
            'fields': (
                'telephone',
                'mobile_phone',
                'name_update_reference',
                'account_type',
                'vip',
                'executive',
                'contractor',
                'security_clearance',
            ),
        }),
    )

    def has_add_permission(self, request):
        return False

    def division(self, instance):
        return instance.cost_centre.get_division_name_display() if instance.cost_centre else ''

    def unit(self, instance):
        return title_except(instance.get_ascender_org_path()[-1]) if instance.get_ascender_org_path() else ''

    def ascender_full_name(self, instance):
        return instance.get_ascender_full_name()
    ascender_full_name.short_description = 'full name'

    def ascender_preferred_name(self, instance):
        return instance.get_ascender_preferred_name()
    ascender_preferred_name.short_description = 'preferred name'

    def ascender_org_path(self, instance):
        path = instance.get_ascender_org_path()
        if path:
            return ' -> '.join(path)
        return ''
    ascender_org_path.short_description = 'organisation path'

    def paypoint(self, instance):
        return instance.get_paypoint()

    def employment_status(self, instance):
        return instance.get_employment_status()

    def geo_location_desc(self, instance):
        return instance.get_geo_location_desc()
    geo_location_desc.short_description = 'Geographic location'

    def position_title(self, instance):
        return instance.get_position_title()

    def position_number(self, instance):
        return instance.get_position_number()

    def job_start_date(self, instance):
        if instance.get_job_start_date():
            return instance.get_job_start_date().strftime('%d-%B-%Y')
        return ''

    def job_end_date(self, instance):
        if instance.get_job_end_date():
            return instance.get_job_end_date().strftime('%d-%B-%Y')
        return ''

    def manager_name(self, instance):
        return instance.get_manager_name()

    def extended_leave(self, instance):
        if instance.get_extended_leave():
            return instance.get_extended_leave().strftime('%d-%B-%Y')
        return ''

    def m365_licence(self, instance):
        return instance.get_licence()

    def get_urls(self):
        urls = super(DepartmentUserAdmin, self).get_urls()
        urls = [
            path('export/', DepartmentUserExport.as_view(), name='departmentuser_export'),
        ] + urls
        return urls


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    fields = ('name', 'ascender_desc')
    list_display = ('name', 'ascender_desc')
    readonly_fields = ('ascender_desc',)
    search_fields = ('name', 'ascender_desc')

    # Disallow creation/deletion of Locations (source of truth if Ascender).
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CostCentre)
class CostCentreAdmin(admin.ModelAdmin):
    fields = ('active', 'code', 'chart_acct_name', 'division_name', 'manager', 'ascender_code')
    list_display = ('code', 'ascender_code', 'chart_acct_name', 'division_name', 'manager', 'active')
    search_fields = ('code', 'chart_acct_name', 'division_name', 'ascender_code')
    list_filter = ('active', 'chart_acct_name', 'division_name')
    readonly_fields = ('manager', 'ascender_code')


@admin.register(AscenderActionLog)
class AscenderActionLogAdmin(admin.ModelAdmin):
    date_hierarchy = 'created'
    fields = ('created', 'level', 'log', 'ascender_data_pprint')
    list_display = ('created', 'level', 'log')
    list_filter = ('level',)
    search_fields = ('log',)

    def ascender_data_pprint(self, obj=None):
        result = ''
        if obj and obj.ascender_data:
            result = json.dumps(obj.ascender_data, indent=4, sort_keys=True)
            result_str = f'<pre>{result}</pre>'
            result = mark_safe(result_str)
        return result
    ascender_data_pprint.short_description = 'ascender data'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
