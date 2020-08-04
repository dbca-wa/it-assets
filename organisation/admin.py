from django import forms
from django.contrib.admin import register, ModelAdmin, SimpleListFilter
from django.urls import path, reverse
from django.utils.html import format_html
from django_mptt_admin.admin import DjangoMpttAdmin
from leaflet.admin import LeafletGeoAdmin
import logging
from reversion.admin import VersionAdmin

from .models import DepartmentUser, ADAction, Location, OrgUnit, CostCentre
from .views import DepartmentUserExport, DepartmentUserDiscrepancyReport

LOGGER = logging.getLogger('sync_tasks')


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


def disable_enable_acount(modeladmin, request, queryset):
    pass
disable_enable_acount.short_description = "Disable or enable selected department user's Active Directory account"


def change_email(modeladmin, request, queryset):
    pass
change_email.short_description = "Change select department user's primary email address in Active Directory"


@register(DepartmentUser)
class DepartmentUserAdmin(VersionAdmin):
    actions = (disable_enable_acount, change_email)
    # Override the default reversion/change_list.html template:
    change_list_template = 'admin/organisation/departmentuser/change_list.html'
    form = DepartmentUserForm
    list_display = (
        'email', 'title', 'employee_id', 'active', 'vip', 'executive', 'cost_centre', 'account_type',
    )
    list_filter = ('account_type', 'active', 'vip', 'executive', 'shared_account')
    search_fields = ('name', 'email', 'title', 'employee_id', 'preferred_name')
    raw_id_fields = ('manager',)
    filter_horizontal = ('secondary_locations',)
    readonly_fields = ('active', 'email')
    fieldsets = (
        ('Active Directory account fields', {
            'description': '<p class="errornote">These fields can be changed using commands in the department user list view.</p>',
            'fields': (
                'active',
                'email',
            ),
        }),
        ('User information fields', {
            'description': '''<p class="errornote">Data in these fields is synchronised with Active Directory.<br>
                Do not edit information in this section without written permission from People Services
                or the cost centre manager (forms are required).</p>''',
            'fields': (
                'name',
                'given_name',
                'surname',
                'title',
                'telephone',
                'mobile_phone',
                'manager',
                'cost_centre',
                'location',
            ),
        }),
        ('Other user metadata fields', {
            'description': '''<p>Data in these fields are not synchronised with Active Directory.</p>''',
            'fields': (
                'preferred_name',
                'extension',
                'home_phone',
                'other_phone',
                'position_type',
                'employee_id',
                'name_update_reference',
                'vip',
                'executive',
                'contractor',
                'notes',
                'working_hours',
                'account_type',
                'security_clearance',
                #'org_unit',
                #'expiry_date',
                #'date_hr_term',
                #'hr_auto_expiry',
                #'secondary_locations',
            ),
        }),
    )

    def get_urls(self):
        urls = super(DepartmentUserAdmin, self).get_urls()
        urls = [
            path('export/', DepartmentUserExport.as_view(), name='departmentuser_export'),
            path('departmentuser-discrepancy-report/', DepartmentUserDiscrepancyReport.as_view(), name='departmentuser_discrepancy_report'),
        ] + urls
        return urls


@register(ADAction)
class AdActionAdmin(ModelAdmin):

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
    list_display = ('created', 'department_user', '__str__', 'completed', 'completed_by')
    list_filter = (CompletedFilter, 'action_type')
    search_fields = ('department_user__name',)


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
class OrgUnitAdmin(DjangoMpttAdmin):
    tree_auto_open = True
    tree_load_on_demand = False
    list_display = (
        'name', 'unit_type', 'users', 'members', 'it_systems', 'cc', 'acronym',
        'manager')
    search_fields = ('name', 'acronym', 'manager__name', 'location__name')
    raw_id_fields = ('manager', 'parent', 'location')
    list_filter = ('unit_type', 'active')

    def users(self, obj):
        from organisation.models import DepartmentUser
        dusers = obj.departmentuser_set.filter(**DepartmentUser.ACTIVE_FILTER)
        return format_html(
            '<a href="{}?org_unit={}">{}</a>',
            reverse('admin:organisation_departmentuser_changelist'),
            obj.pk, dusers.count())

    def members(self, obj):
        return format_html(
            '<a href="{}?org_unit__in={}">{}</a>',
            reverse('admin:organisation_departmentuser_changelist'),
            ','.join([str(o.pk)
                      for o in obj.get_descendants(include_self=True)]),
            obj.members().count()
        )

    def it_systems(self, obj):
        return format_html(
            '<a href="{}?org_unit={}">{}</a>',
            reverse('admin:registers_itsystem_changelist'),
            obj.pk, obj.itsystem_set.count())


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
