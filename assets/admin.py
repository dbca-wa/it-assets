from datetime import date
from django.conf.urls import url
from django.contrib.admin import register, TabularInline
from django.urls import reverse
from django.forms import Form, FileField
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from reversion.admin import VersionAdmin
from io import BytesIO

from .models import Vendor, HardwareModel, HardwareAsset, SoftwareAsset, HardwareInvoice
from .utils import humanise_age, get_csv


@register(Vendor)
class VendorAdmin(VersionAdmin):
    list_display = (
        'name', 'account_rep', 'contact_email', 'contact_phone', 'website',
        'hardware_assets')
    search_fields = ('name', 'details', 'account_rep', 'website')

    def hardware_assets(self, obj):
        return obj.hardwareasset_set.count()


@register(HardwareModel)
class HardwareModelAdmin(VersionAdmin):
    list_display = ('model_no', 'model_type', 'vendor')
    list_filter = ('model_type',)
    search_fields = ('vendor__name', 'model_type', 'model_no')


class HardwareInvoiceInline(TabularInline):
    model = HardwareInvoice
    extra = 1


@register(HardwareAsset)
class HardwareAssetAdmin(VersionAdmin):
    date_hierarchy = 'date_purchased'
    inlines = [HardwareInvoiceInline]
    fieldsets = (
        ('Hardware asset details', {
            'fields': (
                'asset_tag', 'finance_asset_tag', 'serial', 'vendor', 'hardware_model',
                'status', 'notes', 'service_request_url', 'tracked_computer')
        }),
        ('Location & ownership details', {
            'fields': (
                'cost_centre', 'location', 'assigned_user', 'date_purchased',
                'purchased_value', 'is_asset', 'local_property', 'warranty_end')
        }),
        ('Extra data (history)', {
            'fields': ('extra_data_ro',)
        }),
    )
    list_display = (
        'asset_tag', 'vendor', 'model_type', 'hardware_model', 'serial', 'status',
        'age', 'location', 'assigned_user')
    list_filter = ('status', 'vendor')
    raw_id_fields = ('assigned_user',)
    search_fields = (
        'asset_tag', 'vendor__name', 'serial', 'hardware_model__model_type',
        'hardware_model__vendor__name', 'hardware_model__model_no', 'service_request_url',
        'location__name', 'assigned_user__email')
    readonly_fields = ['extra_data_ro']
    # Override the default reversion/change_list.html template:
    change_list_template = 'admin/assets/hardwareasset/change_list.html'

    def model_type(self, obj):
        return obj.hardware_model.model_type

    def age(self, obj):
        if not obj.date_purchased:
            return ''
        d = date.today() - obj.date_purchased
        return humanise_age(d)

    def extra_data_ro(self, obj):
        return obj.get_extra_data_html()
    extra_data_ro.short_description = 'extra data'

    def get_urls(self):
        urls = super(HardwareAssetAdmin, self).get_urls()
        extra_urls = [
            url(
                r'^import/$', self.admin_site.admin_view(self.asset_import),
                name='asset_import'),
            url(
                r'^import/confirm/$', self.admin_site.admin_view(self.asset_import_confirm),
                name='asset_import_confirm'),
            url(r'^export/$', self.hardwareasset_export, name='hardwareasset_export'),
        ]
        return extra_urls + urls

    def hardwareasset_export(self, request):
        """Export all HardwareAssets to a CSV.
        """
        f = get_csv(HardwareAsset.objects.all())
        response = HttpResponse(f.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=hardwareasset_export.csv'
        return response

    class AssetImportForm(Form):
        assets_csv = FileField()

    def asset_import(self, request):
        """Displays a form prompting user to upload CSV containing assets.
        Validates data in the uploaded file and prompts the user for confirmation.
        """
        from .utils import validate_csv  # Avoid circular import.

        if request.method == 'POST':
            form = self.AssetImportForm(request.POST, request.FILES)
            if form.is_valid():
                # Perform validation on the CSV file.
                fileobj = request.FILES['assets_csv']
                (num_assets, errors, warnings, notes) = validate_csv(fileobj)
                context = dict(
                    self.admin_site.each_context(request),
                    title='Hardware asset import',
                    csv=fileobj.read().decode(),  # Read the CSV content as a string.
                    record_count=num_assets,
                    errors=errors,
                    warnings=warnings,
                    notes=notes
                )
                # Stop and complain if we've got errors.
                if errors:
                    return TemplateResponse(
                        request, 'admin/hardwareasset_import_errors.html', context)

                # Otherwise, render the confirmation page.
                return TemplateResponse(
                    request, 'admin/hardwareasset_import_confirm.html', context)
        else:
            form = self.AssetImportForm()

        context = dict(
            self.admin_site.each_context(request),
            form=form,
            title='Hardware asset import'
        )
        return TemplateResponse(
            request, 'admin/hardwareasset_import_start.html', context)

    def asset_import_confirm(self, request):
        """Receives a POST request from the user, indicating that they would
        like to proceed with the import.
        """
        from .utils import validate_csv, import_csv  # Avoid circular import.

        if request.method != 'POST':
            return HttpResponseRedirect(reverse('admin:asset_import'))

        # Build a file object from the CSV data in POST and validate the input
        fileobj = BytesIO(request.POST['csv'].encode())
        (num_assets, errors, warnings, notes) = validate_csv(fileobj)

        context = dict(
            self.admin_site.each_context(request),
            title='Hardware asset import',
            record_count=num_assets,
            errors=errors,
            warnings=warnings,
            notes=notes
        )
        # Stop and complain if we've got errors.
        if errors:
            return TemplateResponse(
                request, 'admin/hardwareasset_import_errors.html', context)

        # Otherwise, render the success page.
        assets_created = import_csv(fileobj)
        context['assets_created'] = assets_created
        context['record_count'] = len(assets_created)
        return TemplateResponse(
            request, 'admin/hardwareasset_import_complete.html', context)


@register(SoftwareAsset)
class SoftwareAssetAdmin(VersionAdmin):
    date_hierarchy = 'date_purchased'
    fieldsets = (
        ('Software asset details', {
            'fields': (
                'name', 'url', 'vendor', 'publisher', 'support', 'support_expiry',
                'purchased_value', 'notes', 'service_request_url')
        }),
        ('License details', {
            'fields': ('license', 'license_details', 'license_count')
        }),
        ('Asset ownership details', {
            'fields': ('cost_centre', 'date_purchased')
        }),
    )
    list_display = ('name', 'vendor', 'license')
    list_filter = ('license',)
    search_fields = ('name', 'vendor__name', 'service_request_url')
