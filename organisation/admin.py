from django import forms
from django.contrib.admin import register, ModelAdmin, SimpleListFilter
from django.urls import path, reverse
from django.utils.html import format_html
from django_q.brokers import get_broker
from django_q.tasks import async_task
from leaflet.admin import LeafletGeoAdmin
from reversion.admin import VersionAdmin

from .models import DepartmentUser, ADAction, Location, OrgUnit, CostCentre
from .utils import deptuser_azure_sync
from .views import DepartmentUserExport


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


@register(DepartmentUser)
class DepartmentUserAdmin(VersionAdmin):

    class AssignedLicenceFilter(SimpleListFilter):
        title = 'assigned licences'
        parameter_name = 'assigned_licences'

        def lookups(self, request, model_admin):
            return (
                ('MICROSOFT 365 E5', 'MICROSOFT 365 E5'),
                ('OFFICE 365 E5', 'OFFICE 365 E5'),
                ('OFFICE 365 E3', 'OFFICE 365 E3'),
                ('OFFICE 365 E1', 'OFFICE 365 E1'),
            )

        def queryset(self, request, queryset):
            if self.value():
                return queryset.filter(assigned_licences__contains=[self.value()])

    actions = ('clear_ad_guid', 'clear_azure_guid')
    # Override the default reversion/change_list.html template:
    change_list_template = 'admin/organisation/departmentuser/change_list.html'
    form = DepartmentUserForm
    list_display = (
        'email', 'title', 'employee_id', 'active', 'vip', 'executive', 'cost_centre', 'account_type',
    )
    list_filter = (AssignedLicenceFilter, 'account_type', 'active', 'vip', 'executive', 'shared_account')
    search_fields = ('name', 'email', 'title', 'employee_id', 'preferred_name')
    raw_id_fields = ('manager',)
    readonly_fields = (
        'active', 'email', 'name', 'given_name', 'surname', 'azure_guid', 'ad_guid',
        'assigned_licences', 'proxy_addresses',
    )
    fieldsets = (
        ('Active Directory account fields', {
            # 'description': '<span class="errornote">These fields can be changed using commands in the department user list view.</span>',
            'fields': (
                'active',
                'email',
                'name',
                'given_name',
                'surname',
            ),
        }),
        ('User information fields', {
            'description': '''<span class="errornote">Data in these fields is synchronised from Active Directory,
                but can be edited here.<br>
                Do not edit information in this section without written permission from People Services
                or the cost centre manager (forms are required).</span>''',
            'fields': (
                'title',
                'telephone',
                'mobile_phone',
                'manager',
                'cost_centre',
                'location',
                'position_type',
                'employee_id',
                'name_update_reference',
            ),
        }),
        ('Other user metadata fields', {
            'description': 'Data in these fields are not synchronised with Active Directory, but may be listed in the Address Book.',
            'fields': (
                'org_unit',
                'preferred_name',
                'extension',
                'home_phone',
                'other_phone',
                'vip',
                'executive',
                'contractor',
                'security_clearance',
                'account_type',
                'notes',
                'working_hours',
            ),
        }),
        ('Office 365 and Active Directory information', {
            'description': 'These data are specific to Office 365 and Active Directory.',
            'fields': (
                'azure_guid',
                'ad_guid',
                'assigned_licences',
                'proxy_addresses',
            ),
        }),
    )

    def get_urls(self):
        urls = super(DepartmentUserAdmin, self).get_urls()
        urls = [
            path('export/', DepartmentUserExport.as_view(), name='departmentuser_export'),
        ] + urls
        return urls

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Run the Azure AD sync actions function, async if a django_q broker is available or synchronously if not.
        broker_available = False
        try:
            broker = get_broker()
            if broker.ping():
                broker_available = True
        except Exception:
            pass

        if broker_available:
            async_task('organisation.utils.deptuser_azure_sync', obj)
        else:
            deptuser_azure_sync(obj)

    def clear_ad_guid(self, request, queryset):
        queryset.update(ad_guid=None)
        self.message_user(request, "On-prem AD GUID has been cleared for the selected user(s)")
    clear_ad_guid.short_description = "Clear a user's on-prem AD GUID following migration between AD instances"

    def clear_azure_guid(self, request, queryset):
        queryset.update(azure_guid=None)
        self.message_user(request, "Azure AD GUID has been cleared for the selected user(s)")
    clear_azure_guid.short_description = "Clear a user's Azure AD GUID"


@register(ADAction)
class ADActionAdmin(ModelAdmin):

    class CompletedFilter(SimpleListFilter):
        """SimpleListFilter to filter on True/False if an object has a value for completed.
        """
        title = 'completed'
        parameter_name = 'completed_boolean'

        def lookups(self, request, model_admin):
            return (
                ('true', 'Complete'),
                ('false', 'Incomplete'),
            )

        def queryset(self, request, queryset):
            if self.value() == 'true':
                return queryset.filter(completed__isnull=False)
            if self.value() == 'false':
                return queryset.filter(completed__isnull=True)

    date_hierarchy = 'created'
    fields = ('department_user', 'action_type', 'ad_field', 'field_value', 'completed')
    list_display = ('created', 'department_user', 'azure_guid', 'action', 'completed', 'completed_by')
    list_filter = (CompletedFilter, 'action_type')
    readonly_fields = ('department_user', 'action_type', 'ad_field', 'field_value', 'completed')
    search_fields = ('department_user__name',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@register(Location)
class LocationAdmin(LeafletGeoAdmin):
    list_display = ('name', 'address', 'phone', 'fax', 'email', 'manager')
    list_filter = ('active',)
    raw_id_fields = ('manager',)
    search_fields = ('name', 'address', 'phone', 'fax', 'email', 'manager__email')
    settings_overrides = {
        'DEFAULT_CENTER': (-31.0, 115.0),
        'DEFAULT_ZOOM': 5
    }


@register(OrgUnit)
class OrgUnitAdmin(ModelAdmin):
    list_display = ('name', 'unit_type', 'division_unit', 'users', 'cc', 'manager', 'active')
    search_fields = ('name', 'acronym', 'manager__name', 'location__name')
    raw_id_fields = ('manager',)
    list_filter = ('unit_type', 'active')

    def users(self, obj):
        from organisation.models import DepartmentUser
        dusers = obj.departmentuser_set.filter(**DepartmentUser.ACTIVE_FILTER)
        return format_html(
            '<a href="{}?org_unit={}">{}</a>',
            reverse('admin:organisation_departmentuser_changelist'),
            obj.pk, dusers.count())


@register(CostCentre)
class CostCentreAdmin(ModelAdmin):
    list_display = (
        'code', 'chart_acct_name', 'division_name', 'users', 'manager', 'business_manager', 'active'
    )
    search_fields = ('code', 'chart_acct_name', 'org_position__name', 'division_name')
    list_filter = ('active', 'chart_acct_name', 'division_name')
    raw_id_fields = ('org_position', 'manager', 'business_manager', 'admin', 'tech_contact')

    def users(self, obj):
        return format_html(
            '<a href="{}?cost_centre={}">{}</a>',
            reverse('admin:organisation_departmentuser_changelist'),
            obj.pk, obj.departmentuser_set.count()
        )
