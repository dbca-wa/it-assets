from django import forms
from django.conf.urls import url
from django.contrib import messages
from django.contrib.admin import register, site, ModelAdmin
from django.urls import reverse
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django_mptt_admin.admin import DjangoMpttAdmin
from django_q.tasks import async_task
from leaflet.admin import LeafletGeoAdmin
import logging
from reversion.admin import VersionAdmin
from threading import Thread
import time

from .models import DepartmentUser, Location, OrgUnit, CostCentre
from .tasks import alesco_data_import
from .utils import departmentuser_csv_report

LOGGER = logging.getLogger('sync_tasks')


def delayed_save(obj):
    """Wait one second, then call save() for the passed-in object.
    """
    time.sleep(1)
    obj.save()


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
    # Override the default reversion/change_list.html template:
    change_list_template = 'admin/organisation/departmentuser/change_list.html'
    form = DepartmentUserForm
    list_display = [
        'email', 'title', 'employee_id', 'username', 'active', 'vip', 'executive',
        'cost_centre', 'account_type', 'o365_licence']
    list_filter = [
        'account_type', 'active', 'vip', 'executive', 'shared_account',
        'o365_licence']
    search_fields = ['name', 'email', 'username', 'employee_id', 'preferred_name']
    raw_id_fields = ['parent', 'cost_centre', 'org_unit']
    filter_horizontal = ['secondary_locations']
    readonly_fields = [
        'username', 'org_data_pretty', 'ad_data_pretty',
        'active', 'in_sync', 'ad_deleted', 'date_ad_updated',
        'alesco_data_pretty', 'o365_licence', 'shared_account']
    fieldsets = (
        ('Email/username', {
            'fields': ('email', 'username'),
        }),
        ('Name and organisational fields', {
            'description': '''<p class="errornote">Do not edit information in this section
            without written permission from People Services or the cost centre manager
            (forms are required).</p>''',
            'fields': (
                'given_name', 'surname', 'name', 'employee_id', 'cost_centre',
                'org_unit', 'location', 'parent', 'security_clearance', 'name_update_reference'),
        }),
        ('Account fields', {
            'fields': ('account_type', 'expiry_date', 'contractor', 'notes'),
        }),
        ('Other details', {
            'fields': (
                'vip', 'executive', 'populate_primary_group',
                'preferred_name', 'photo', 'title', 'position_type',
                'telephone', 'mobile_phone', 'extension', 'other_phone',
                'secondary_locations', 'working_hours', 'extra_data',
            )
        }),
        ('AD sync and HR data', {
            'fields': (
                'ad_guid',
                'ad_dn',
                'azure_guid',
                'active', 'in_sync', 'ad_deleted', 'date_ad_updated',
                'o365_licence', 'shared_account',
                'org_data_pretty', 'ad_data_pretty', 'alesco_data_pretty',
            )
        })
    )

    def save_model(self, request, obj, form, change):
        """Override save_model in order to log any changes to some fields:
        'given_name', 'surname', 'employee_id', 'cost_centre', 'name', 'org_unit'
        """
        l = 'DepartmentUser: {}, field: {}, original_value: {} new_value: {}, changed_by: {}, reference: {}'
        if obj._DepartmentUser__original_given_name != obj.given_name:
            LOGGER.info(l.format(
                obj.email, 'given_name', obj._DepartmentUser__original_given_name, obj.given_name,
                request.user.username, obj.name_update_reference
            ))
        if obj._DepartmentUser__original_surname != obj.surname:
            LOGGER.info(l.format(
                obj.email, 'surname', obj._DepartmentUser__original_surname, obj.surname,
                request.user.username, obj.name_update_reference
            ))
        if obj._DepartmentUser__original_employee_id != obj.employee_id:
            LOGGER.info(l.format(
                obj.email, 'employee_id', obj._DepartmentUser__original_employee_id,
                obj.employee_id, request.user.username, obj.name_update_reference
            ))
        if obj._DepartmentUser__original_cost_centre_id != obj.cost_centre_id:
            LOGGER.info(l.format(
                obj.email, 'cost_centre', CostCentre.objects.filter(id=obj._DepartmentUser__original_cost_centre_id).first(),
                obj.cost_centre, request.user.username, obj.name_update_reference
            ))
        if obj._DepartmentUser__original_name != obj.name:
            LOGGER.info(l.format(
                obj.email, 'name', obj._DepartmentUser__original_name, obj.name,
                request.user.username, obj.name_update_reference
            ))
        if obj._DepartmentUser__original_org_unit_id != obj.org_unit_id:
            LOGGER.info(l.format(
                obj.email, 'org_unit', OrgUnit.objects.filter(id=obj._DepartmentUser__original_org_unit_id).first(), obj.org_unit,
                request.user.username, obj.name_update_reference
            ))
        if obj._DepartmentUser__original_expiry_date != obj.expiry_date:
            LOGGER.info(l.format(
                obj.email, 'expiry_date', obj._DepartmentUser__original_expiry_date, obj.expiry_date,
                request.user.username, obj.name_update_reference
            ))
        obj.save()
        # NOTE: following a change to a DepartmentUser object, we need to call
        # save a second time so that the org_data field is correct. The lines
        # below will do so in a separate thread.
        t = Thread(target=delayed_save, args=(obj,))
        t.start()

    def get_urls(self):
        urls = super(DepartmentUserAdmin, self).get_urls()
        urls = [
            url(r'^alesco-import/$', self.admin_site.admin_view(self.alesco_import), name='alesco_import'),
            url(r'^export/$', self.admin_site.admin_view(self.export), name='departmentuser_export'),
        ] + urls
        return urls

    class AlescoImportForm(forms.Form):
        spreadsheet = forms.FileField()

    def alesco_import(self, request):
        """Displays a form prompting user to upload an Excel spreadsheet of
        employee data from Alesco. Temporary measure until database link is
        worked out.
        """
        context = dict(
            site.each_context(request),
            title='Alesco data import'
        )

        if request.method == 'POST':
            form = self.AlescoImportForm(request.POST, request.FILES)
            if form.is_valid():
                upload = request.FILES['spreadsheet']
                # Run the task asynchronously.
                async_task(alesco_data_import, upload)
                messages.info(request, 'Alesco data spreadsheet uploaded successfully; data is now being processed.')
                return redirect('admin:organisation_departmentuser_changelist')
        else:
            form = self.AlescoImportForm()
        context['form'] = form

        return TemplateResponse(request, 'organisation/alesco_import.html', context)

    def export(self, request):
        """Exports DepartmentUser data to a CSV, and returns
        """
        data = departmentuser_csv_report()
        response = HttpResponse(data, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=departmentuser_export.csv'
        return response


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
        'name', 'code', 'chart_acct_name', 'org_position', 'division', 'users', 'manager',
        'business_manager', 'admin', 'tech_contact', 'active')
    search_fields = (
        'name', 'code', 'chart_acct_name', 'org_position__name', 'division__name',
        'org_position__acronym', 'division__acronym')
    list_filter = ('active', 'chart_acct_name')
    raw_id_fields = (
        'org_position', 'manager', 'business_manager', 'admin', 'tech_contact')

    def users(self, obj):
        return format_html(
            '<a href="{}?cost_centre={}">{}</a>',
            reverse('admin:organisation_departmentuser_changelist'),
            obj.pk, obj.departmentuser_set.count())
