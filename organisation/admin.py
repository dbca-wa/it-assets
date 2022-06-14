from django import forms
from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from leaflet.admin import LeafletGeoAdmin

from itassets.utils import ModelDescMixin
from .models import DepartmentUser, Location, OrgUnit, CostCentre
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

    #actions = ('clear_ad_guid', 'clear_azure_guid')
    change_list_template = 'admin/organisation/departmentuser/change_list.html'
    form = DepartmentUserForm
    list_display = (
        'email', 'name', 'title', 'employee_id', 'active', 'cost_centre', 'division', 'unit', 'account_type',
    )
    list_filter = (AssignedLicenceFilter, 'active', 'account_type', 'shared_account')
    model_description = DepartmentUser.__doc__
    search_fields = ('name', 'email', 'title', 'employee_id', 'ad_guid', 'azure_guid')
    raw_id_fields = ('manager',)
    readonly_fields = (
        'active', 'email', 'name', 'given_name', 'surname', 'azure_guid', 'ad_guid', 'ascender_full_name', 'ascender_preferred_name',
        'assigned_licences', 'proxy_addresses', 'dir_sync_enabled', 'ascender_org_path', 'geo_location_desc',
        'paypoint', 'employment_status', 'position_title', 'job_start_date', 'job_end_date', 'ascender_data_updated',
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

    def get_urls(self):
        urls = super(DepartmentUserAdmin, self).get_urls()
        urls = [
            path('export/', DepartmentUserExport.as_view(), name='departmentuser_export'),
        ] + urls
        return urls

    def clear_ad_guid(self, request, queryset):
        # Action: allow a user's onprem AD GUID value to be cleared.
        queryset.update(ad_guid=None)
        self.message_user(request, "On-prem AD GUID has been cleared for the selected user(s)")
    clear_ad_guid.short_description = "Clear a user's on-prem AD GUID following migration between AD instances"

    def clear_azure_guid(self, request, queryset):
        # Action: allow a user's Azure GUID value to be cleared.
        queryset.update(azure_guid=None)
        self.message_user(request, "Azure AD GUID has been cleared for the selected user(s)")
    clear_azure_guid.short_description = "Clear a user's Azure AD GUID"


@admin.register(Location)
class LocationAdmin(LeafletGeoAdmin):
    fields = ('name', 'address', 'pobox', 'phone', 'fax', 'point', 'active', 'ascender_desc')
    list_display = ('name', 'address', 'phone', 'fax', 'active')
    list_filter = ('active',)
    readonly_fields = ('ascender_desc',)
    search_fields = ('name', 'address', 'phone', 'fax')
    settings_overrides = {
        'DEFAULT_CENTER': (-31.0, 115.0),
        'DEFAULT_ZOOM': 5
    }


#@admin.register(OrgUnit)
class OrgUnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'division_unit', 'location', 'users', 'cc', 'active')
    fields = ('active', 'name', 'location', 'division_unit', 'ascender_clevel')
    search_fields = ('name', 'location__name', 'ascender_clevel')
    readonly_fields = ('division_unit', 'ascender_clevel')
    list_filter = ('active',)

    def users(self, obj):
        from organisation.models import DepartmentUser
        dusers = obj.departmentuser_set.filter(**DepartmentUser.ACTIVE_FILTER)
        return format_html(
            '<a href="{}?org_unit={}">{}</a>',
            reverse('admin:organisation_departmentuser_changelist'),
            obj.pk, dusers.count())


@admin.register(CostCentre)
class CostCentreAdmin(admin.ModelAdmin):
    fields = ('active', 'code', 'chart_acct_name', 'division_name', 'manager', 'ascender_code')
    list_display = ('code', 'ascender_code', 'chart_acct_name', 'division_name', 'manager', 'active')
    search_fields = ('code', 'chart_acct_name', 'division_name', 'ascender_code')
    list_filter = ('active', 'chart_acct_name', 'division_name')
    readonly_fields = ('manager', 'ascender_code')
