from django import forms
from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.views.generic import TemplateView
from leaflet.admin import LeafletGeoAdmin

from .models import DepartmentUser, ADAction, Location, OrgUnit, CostCentre
from .views import DepartmentUserExport, DepartmentUserAscenderDiscrepancyExport


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
class DepartmentUserAdmin(admin.ModelAdmin):

    class UpdateUserDataFromAscender(TemplateView):
        """A small custom view to allow confirmation of updating department users from cached
        Ascender data.
        """
        template_name = 'admin/ascender_update_confirm.html'

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            if 'pks' in self.request.GET and self.request.GET['pks']:
                context['user_pks'] = self.request.GET['pks']
                pks = self.request.GET['pks'].split(',')
                context['department_users'] = DepartmentUser.objects.filter(pk__in=pks, employee_id__isnull=False)
            # Get the admin site context (we passed in the ModelAdmin class as a kwarg via the URL pattern).
            context['opts'] = DepartmentUser._meta
            context['title'] = 'Update user data from Ascender'
            # Include the admin site context.
            context.update(admin.site.each_context(self.request))
            return context

        def post(self, request, *args, **kwargs):
            pks = self.request.POST['user_pks'].split(',')
            users = DepartmentUser.objects.filter(pk__in=pks, employee_id__isnull=False)
            updates = 0
            for user in users:
                discrepancies = user.get_ascender_discrepancies()
                if discrepancies:
                    for d in discrepancies:
                        setattr(user, d['field'], d['new_value'])
                    user.save()
                    updates += 1
            messages.success(request, f'{updates} user(s) have been updated')
            return HttpResponseRedirect(reverse('admin:organisation_departmentuser_changelist'))

    class AssignedLicenceFilter(admin.SimpleListFilter):
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

    actions = ('clear_ad_guid', 'clear_azure_guid', 'update_data_from_ascender')
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
        'assigned_licences', 'proxy_addresses', 'dir_sync_enabled', 'cost_centre',
        'employment_status', 'job_start_date', 'job_termination_date', 'ascender_data_updated',
    )
    fieldsets = (
        ('Microsoft 365, Azure AD and on-prem AD account information', {
            'description': '<span class="errornote">Data in these fields is maintained in Azure Active Directory.</span>',
            'fields': (
                'active',
                'email',
                'name',
                'given_name',
                'surname',
                'azure_guid',
                'ad_guid',
                'assigned_licences',
                'proxy_addresses',
                'dir_sync_enabled',
            ),
        }),
        ('Ascender account information', {
            'description': '''<span class="errornote">These data are specific to the Ascender HR database.
            The employee ID must be set in order to enable synchronisation from Ascender.</span>''',
            'fields': (
                'employee_id',
                'cost_centre',
                'employment_status',
                'job_start_date',
                'job_termination_date',
                'ascender_data_updated',
            ),
        }),
        ('User information fields', {
            'description': '''<span class="errornote">Data in these fields should match information from Ascender,
                but can be edited here for display in the Address Book.<br>
                Do not edit information in this section without written permission from People Services
                or the cost centre manager (forms are required).</span>''',
            'fields': (
                'title',
                'telephone',
                'mobile_phone',
                'manager',
                'location',
                'name_update_reference',
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
            ),
        }),
    )

    def employment_status(self, instance):
        return instance.get_employment_status()

    def job_start_date(self, instance):
        if instance.get_job_start_date():
            return instance.get_job_start_date().strftime('%d-%B-%Y')
        return ''

    def job_termination_date(self, instance):
        if instance.get_job_term_date():
            return instance.get_job_term_date().strftime('%d-%B-%Y')
        return ''

    def get_urls(self):
        urls = super(DepartmentUserAdmin, self).get_urls()
        urls = [
            path('export/', DepartmentUserExport.as_view(), name='departmentuser_export'),
            path('ascender-discrepancies/', DepartmentUserAscenderDiscrepancyExport.as_view(), name='ascender_discrepancies'),
            path('ascender-update/', self.UpdateUserDataFromAscender.as_view(), name='ascender_update'),
        ] + urls
        return urls

    def save_model(self, request, obj, form, change):
        """Following save, carry out any required sync actions.
        """
        super().save_model(request, obj, form, change)
        # Run the Ascender/Azure AD/on-prem AD update actions.
        obj.update_from_ascender_data()
        obj.update_from_azure_ad_data()
        obj.update_from_onprem_ad_data()
        actions = obj.generate_ad_actions()
        if actions:
            self.message_user(request, "AD action(s) have been generated for {}".format(obj))
        obj.audit_ad_actions()

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

    def update_data_from_ascender(self, request, queryset):
        # Action: allow a user to have data updated from cached Ascender data.
        selected = queryset.values_list('pk', flat=True)
        # Redirect to the URL for the view to confirm this action.
        return HttpResponseRedirect('{}?pks={}'.format(
            reverse('admin:ascender_update'), ','.join(str(pk) for pk in selected),
        ))
    update_data_from_ascender.short_description = "Update a user's information from cached Ascender data"


@admin.register(ADAction)
class ADActionAdmin(admin.ModelAdmin):

    class CompletedFilter(admin.SimpleListFilter):
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


@admin.register(Location)
class LocationAdmin(LeafletGeoAdmin):
    list_display = ('name', 'address', 'phone', 'fax', 'email', 'manager', 'active')
    list_filter = ('active',)
    raw_id_fields = ('manager',)
    search_fields = ('name', 'address', 'phone', 'fax', 'email', 'manager__email')
    settings_overrides = {
        'DEFAULT_CENTER': (-31.0, 115.0),
        'DEFAULT_ZOOM': 5
    }


@admin.register(OrgUnit)
class OrgUnitAdmin(admin.ModelAdmin):
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


@admin.register(CostCentre)
class CostCentreAdmin(admin.ModelAdmin):
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
