import csv
from datetime import datetime
from django import forms
from django.conf.urls import url
from django.contrib.admin import AdminSite, ModelAdmin, register
from django.core.urlresolvers import reverse
from django.forms import ModelForm, ValidationError
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from djqscsv import render_to_csv_response
import re
from reversion.admin import VersionAdmin
from StringIO import StringIO

from assets.models import Supplier, Model, Asset, Location, Invoice


class AssetsAdminSite(AdminSite):
    site_header = 'DPaW IT Asset Management'
admin_site = AssetsAdminSite(name='myadmin')


class AuditAdmin(VersionAdmin, ModelAdmin):
    list_display = ['__unicode__', 'creator', 'modifier', 'created', 'modified']
    search_fields = [
        'id', 'creator__username', 'modifier__username', 'creator__email',
        'modifier__email']
    raw_id_fields = ['creator', 'modifier']


def export_supplier_assets(modeladmin, request, queryset):
    queryset = Asset.objects.filter(model__manufacturer__in=queryset)
    return export_assets_csv(modeladmin, request, queryset)
export_supplier_assets.short_description = 'Export assets by selected suppliers as CSV'


@register(Supplier, site=admin_site)
class SupplierAdmin(AuditAdmin):
    list_display = ['name', 'get_account_rep', 'get_website', 'get_assets']
    search_fields = [
        'name', 'account_rep', 'contact_email', 'contact_phone', 'website', 'notes']
    actions = [export_supplier_assets]


def export_model_assets(modeladmin, request, queryset):
    queryset = Asset.objects.filter(model__in=queryset)
    return export_assets_csv(modeladmin, request, queryset)
export_model_assets.short_description = 'Export assets of selected models as CSV'


@register(Model, site=admin_site)
class AssetModelAdmin(AuditAdmin):
    list_display = ['manufacturer', 'model', 'model_type', 'get_assets', 'notes']
    list_filter = ['manufacturer']
    search_fields = ['manufacturer__name', 'model', 'notes', 'model_type']
    actions = [export_model_assets]

    def get_urls(self):
        urls = super(AssetModelAdmin, self).get_urls()
        extra_urls = [
            url(r'^categories/$', self.categories, name='model_categories'),
        ]
        return extra_urls + urls

    def categories(self, request):
        """Prints a list of categories for the model_type field.
        """
        context = dict(
            self.admin_site.each_context(request),
            categories=[i for (i, j) in Model.type_choices]
        )
        return TemplateResponse(request, 'assets/categories.html', context)


class AssetAdminForm(ModelForm):
    class Meta:
        fields = '__all__'
        model = Asset

    def clean_asset_tag(self):
        """Validates that an asset tag is of the form ITXXXXX.
        """
        # Asset tags should always be uppercase
        data = self.cleaned_data['asset_tag'].upper()
        asset_tag_re = re.compile("^IT\d{5}$")
        if not asset_tag_re.match(data):
            raise ValidationError("Please enter a valid asset tag.")
        return data


def export_assets_csv(modeladmin, request, queryset):
    field_header_map = {
        'model__manufacturer__name': 'manufacturer',
        'model__model': 'model',
        'model__model_type': 'model type',
        'location__name': 'location',
        'location__block': 'block',
        'location__site': 'site',
    }
    # Turn queryset into a ValuesQuerySet
    queryset = queryset.values(
        'id', 'asset_tag', 'finance_asset_tag', 'model__manufacturer__name',
        'model__model', 'model__model_type', 'status', 'serial', 'date_purchased',
        'purchased_value', 'location__name', 'location__block', 'location__site',
        'assigned_user', 'notes')
    return render_to_csv_response(queryset, field_header_map=field_header_map)
export_assets_csv.short_description = 'Export selected assets as CSV'


class ImportForm(forms.Form):
    assets_to_import = forms.FileField()


@register(Asset, site=admin_site)
class AssetAdmin(AuditAdmin):
    list_display = [
        'asset_tag', 'get_type', 'get_model', 'serial', 'status', 'get_age',
        'get_location', 'get_assigned_user']
    list_filter = ['model__manufacturer', 'status', 'location__site', 'date_purchased']
    date_hierarchy = 'date_purchased'
    search_fields = [
        'asset_tag', 'model__model', 'status', 'model__manufacturer__name',
        'model__model_type', 'location__name', 'location__block', 'location__site',
        'assigned_user', 'serial', 'invoice__supplier_ref', 'invoice__job_number',
        'invoice__cost_centre_number', 'invoice__etj_number']
    form = AssetAdminForm
    actions = [export_assets_csv]

    def get_urls(self):
        urls = super(AssetAdmin, self).get_urls()
        extra_urls = [
            url(r'^import/$', self.asset_import, name='asset_import'),
            url(r'^import/final$', self.do_import, name='asset_do_import'),
        ]
        return extra_urls + urls

    def asset_import(self, request):
        """
        Displays a form prompting user to upload CSV containing assets. Passes
        uploaded file object to confirm_import to validate data and prompt the user
        for confirmation.
        """
        if request.method == 'POST':
            form = ImportForm(request.POST, request.FILES)
            if form.is_valid():
                return self.confirm_import(request, request.FILES['assets_to_import'])
        else:
            form = ImportForm()

        context = dict(
            self.admin_site.each_context(request),
            form=form,
            title='Bulk import'
        )
        return TemplateResponse(request, 'assets/import_intro.html', context)

    def confirm_import(self, request, fileobj):
        """
        Receives a file object from import_asset, and does validation, shows a
        confirmation/error page and finally does the actual import.
        """
        # Perform validation on the input given to us
        (num_assets, errors, warnings, notes) = self.validate_import(fileobj)

        context = dict(
            self.admin_site.each_context(request),
            title='Bulk import',
            csv=fileobj.read(),
            record_count=num_assets,
            errors=errors,
            warnings=warnings,
            notes=notes
        )
        # Stop and complain if we've got errors
        if errors:
            return TemplateResponse(request, 'assets/import_criticalerrors.html', context)

        # Otherwise, render the confirmation page
        return TemplateResponse(request, 'assets/import_confirm.html', context)

    def do_import(self, request):
        """
        Receives a POST request from the user, indicating that they would like to
        proceed with the import.
        """
        if request.method != 'POST':
            return HttpResponseRedirect(reverse('admin:asset_import'))

        # Build a file object from the CSV data in POST and validate the input
        fileobj = StringIO(request.POST['csv'])
        (num_assets, errors, warnings, notes) = self.validate_import(fileobj)

        context = dict(
            self.admin_site.each_context(request),
            title='Bulk import',
            record_count=num_assets,
            errors=errors,
            warnings=warnings,
            notes=notes
        )

        if errors:
            return TemplateResponse(request, 'assets/import_criticalerrors.html', context)

        assets_created = []
        c = csv.DictReader(fileobj)
        for row in c:
            # Get the manufacturer and model first, and create if required
            try:
                ma = Supplier.objects.filter(
                    name__iexact=row['manufacturer'])[0]
            except IndexError:
                ma = Supplier(name=row['manufacturer'])
                ma.save()
            try:
                mo = Model.objects.filter(
                    manufacturer=ma, model__iexact=row['model'])[0]
            except IndexError:
                mo = Model(
                    manufacturer=ma,
                    model=row['model'],
                    model_type=row['model type'])
                mo.save()
            try:
                loc = Location.objects.filter(
                    name__iexact=row['location'],
                    block__iexact=row['block'],
                    site__iexact=row['site'])[0]
            except IndexError:
                # This should never happen, but abort gracefully if it does
                context['errors'] = [
                    'Line {}: A critical error occurred while attempting to load the location record.'.format(c.line_num)
                ]
                context['warnings'] = ''
                context['notes'] = ''
                return TemplateResponse(request, 'assets/import_criticalerrors.html', context)

            # Set default values for optional fields if necessary
            try:
                fat = row['finance asset tag']
            except KeyError:
                fat = ''
            try:
                pv = row['purchased value'].strip()
            except KeyError:
                pv = None
            if pv == '':
                pv = None
            try:
                assigned_user = row['assigned user']
            except KeyError:
                assigned_user = ''

            try:
                notes = row['notes']
            except KeyError:
                notes = ''
            if row['serial'] == 'Unknown':
                serial = row['serial']
            else:
                serial = row['serial'].upper()
            # Finally, create the asset record
            asset = Asset(
                asset_tag=row['asset tag'].upper(),
                finance_asset_tag=fat,
                model=mo,
                status=row['status'].capitalize(),
                serial=serial,
                date_purchased=datetime.strptime(
                    row['date purchased'], '%d/%m/%Y'),
                purchased_value=pv,
                location=loc,
                assigned_user=assigned_user,
                notes=notes,
            )
            asset.save()
            assets_created.append(asset)

        context['record_count'] = len(assets_created)
        context['assets_created'] = assets_created
        return TemplateResponse(request, 'assets/import_complete.html', context)

    def validate_import(self, fileobj):
        """Performs validation on the CSV file at fileobj.
        Returns a tuple (num_assets, errors, warnings, notes).
        """
        try:
            c = csv.DictReader(fileobj)
            c.fieldnames
        except Exception:
            errors = ["""The file you uploaded could not be interpreted. Check that
                you uploaded the correct file (in a .csv format) and try again."""]
            return (0, errors, [], [])

        critical_fields = (
            'asset tag', 'manufacturer', 'model', 'serial', 'date purchased',
            'location', 'block', 'site')
        all_fields = critical_fields + (
            'ID', 'finance asset tag', 'model type', 'status', 'purchased value',
            'assigned user', 'notes')

        # List to hold errors found during the validation process
        errors = []
        warnings = []
        notes = []

        # List of asset tags, to confirm uniqueness
        asset_tag_list = []

        # Inspect the first row to see what columns we've got
        for field in critical_fields:
            if field not in c.fieldnames:
                errors.append(
                    'The mandatory column {} is missing from the spreadsheet.'.format(field))

        for field in c.fieldnames:
            if field not in all_fields:
                warnings.append('''Your spreadsheet contains an unknown column '{}'.
                    This column will be ignored during the import process.'''.format(field))

        if 'status' not in c.fieldnames:
            warnings.append('''Your spreadsheet does not contain a column called
                'status' - the status field of every new asset will be set to
                'In storage'.''')

        # Inspect each row and do field-specific validation
        for row in c:
            # Check asset tag syntax
            asset_tag_re = re.compile("^IT\d{5}$")
            try:
                if not row['asset tag']:
                    errors.append(
                        "Line {}: A value for the asset tag column is missing. Enter a value to continue.".format(c.line_num))
                elif not asset_tag_re.match(row['asset tag'].upper()):
                    errors.append(
                        "Line {}: The value '{}' in the asset tag column is invalid. Asset tags should be in the form ITXXXXX.".format(c.line_num, row['asset tag']))
                if row['asset tag'].upper() in asset_tag_list:
                    errors.append(
                        "Line {}: The asset tag '{}' exists in several locations in the spreadsheet. Asset tags are unique - remove the duplicate values to continue.".format(c.line_num, row['asset tag']))

                asset_tag_list.append(row['asset tag'].upper())

                if Asset.objects.get(asset_tag__iexact=row['asset tag']):
                    errors.append(
                        "Line {}: The asset tag '{}' already exists in the database. Asset tags must be unique.".format(c.line_num, row['asset tag']))
            except KeyError:
                # Missing fields will have been caught above
                pass
            except Asset.DoesNotExist:
                # This is ok, it means there's no duplicate asset in the database
                pass

            # Check finance asset tag
            try:
                if row['finance asset tag']:
                    finance_asset_tag_re = re.compile("^\d+$")
                    if not finance_asset_tag_re.match(row['finance asset tag']):
                        warnings.append(
                            "Line {}: The finance asset tag '{}' contains numbers and other characters - these tags usually only contain numbers. Check the tag is correct before proceeding.".format(c.line_num, row['finance asset tag']))
            except KeyError:
                # Missing fields will have been caught above
                pass

            # Check manufacturer
            try:
                if not row['manufacturer']:
                    errors.append(
                        "Line {}: The mandatory field 'manufacturer' is blank.".format(c.line_num))
                if not Supplier.objects.filter(
                        name__iexact=row['manufacturer']) and row['manufacturer']:
                    notes.append(
                        "Line {}: Manufacturer '{}' is unknown - a new manufacturer record will be created.".format(c.line_num, row['manufacturer']))
            except KeyError:
                # Missing fields will have been caught above
                pass

            # Check model
            try:
                if not row['model']:
                    errors.append(
                        "Line {}: The mandatory field 'model' is blank.".format(c.line_num))
                if not Model.objects.filter(manufacturer__name__iexact=row['manufacturer']).filter(
                        model__iexact=row['model']) and row['manufacturer'] and row['model']:
                    notes.append(
                        "Model '{} {}' on line {} is unknown - a new model record will be created.".format(row['manufacturer'], row['model'], c.line_num))
                if not Model.objects.filter(manufacturer__name__iexact=row['manufacturer']).filter(model__iexact=row['model']) and row[
                        'manufacturer'] and row['model'] and ('model_lifecycle' not in row.keys() or not row['model_lifecycle']):
                    errors.append(
                        "Line {}: A new model is to be created, and model_lifecycle has not been specified. Enter a value to continue.".format(c.line_num))
                if not Model.objects.filter(manufacturer__name__iexact=row['manufacturer']).filter(model__iexact=row['model']) and row[
                        'manufacturer'] and row['model'] and ('model_type' not in row.keys() or not row['model_type']):
                    errors.append(
                        "Line {}: A new model is to be created, and model_type has not been specified. Enter a value to continue.".format(c.line_num))
            except KeyError:
                # Missing fields will have been caught above
                pass

            # Check model_lifecycle
            try:
                i = int(row['model_lifecycle'])
                if i < 0:
                    raise ValueError
            except KeyError:
                # Missing fields will have been caught above
                pass
            except ValueError:
                # An error is generated above (under model) if model_type is blank
                if row['model_lifecycle']:
                    errors.append(
                        "Line %d: The value '%s' in the model_lifecycle column is invalid. The model_lifecycle field should consist of a single positive number." %
                        (c.line_num, row['model_lifecycle']))

            # Check model type
            try:
                # An error is generated above (under model) if model_type is blank
                if row['model type'] and (row['model type'], row['model type']) not in Model.type_choices:
                    errors.append(
                        "Line {}: The value '{}' in the model_type column is not a valid category. Check the <a href='/assets/categories'>list of categories</a> and correct the value. Note this field is case-sensitive.".format(c.line_num, row['model_type']))
            except KeyError:
                # Missing fields will have been caught above
                pass

            # Check status
            try:
                s = row['status'].capitalize()
                if s != 'In storage' and s != 'Deployed' and s != 'Disposed':
                    errors.append(
                        "Line {}: The value '{}' in the status column is invalid. The asset status must be one of 'In storage', 'Deployed' or 'Disposed'.".format(c.line_num, row['status']))
            except KeyError:
                # Missing fields will have been caught above
                pass

            # Check serial
            try:
                if not row['serial']:
                    errors.append(
                        "Line {}: The mandatory field 'serial' is blank. If the device does not have a serial number, enter 'Unknown'.".format(c.line_num))
            except KeyError:
                # Missing fields will have been caught above
                pass

            # Check date purchased
            try:
                if not row['date purchased']:
                    errors.append(
                        "Line {}: The mandatory field 'date_purchased' is blank.".format(c.line_num))
                datetime.strptime(row['date purchased'], '%d/%m/%Y')
            except KeyError:
                # Missing fields will have been caught above
                pass
            except ValueError:
                errors.append(
                    "Line {}: The value '{}' in the date_purchased column is invalid. Dates must be in the form dd/mm/yyyy.".format(c.line_num, row['date_purchased']))

            # Check purchased value
            try:
                purchased_value_re = re.compile("^([0-9]*|\d*\.\d{1}?\d*)$")
                if not purchased_value_re.match(row['purchased value'].strip()):
                    errors.append(
                        "Line {}: The value '{}' in the purchased value column is invalid. Values must be a simple positive decimal number (no $ sign or commas).".format(c.line_num, row['purchased value'].strip()))
            except KeyError:
                # Missing fields will have been caught above
                pass

            # Check location fields
            try:
                if not Location.objects.filter(name__iexact=row['location']).filter(
                        block__iexact=row['block']).filter(site__iexact=row['site']):
                    errors.append(
                        "Line {}: There is no defined location matching {}, {}, {}. Locations must be pre-defined in the Locations table before importing data.".format(c.line_num, row['location'], row['block'], row['site']))
            except KeyError:
                # Missing fields will have been caught above
                pass

        # Reset fileobj now we're finished with it
        fileobj.seek(0)

        return (len(asset_tag_list), errors, warnings, notes)


def export_location_assets(modeladmin, request, queryset):
    """Custom action to export assets for chosen location(s).
    """
    queryset = Asset.objects.filter(location__in=queryset)
    return export_assets_csv(modeladmin, request, queryset)
export_location_assets.short_description = 'Export assets at selected locations as CSV'


@register(Location, site=admin_site)
class LocationAdmin(AuditAdmin):
    list_display = ('name', 'block', 'site', 'get_assets')
    search_fields = ('name', 'block', 'site')
    actions = [export_location_assets]


@register(Invoice, site=admin_site)
class InvoiceAdmin(AuditAdmin):
    list_display = [
        'job_number', 'supplier', 'supplier_ref', 'total_value', 'get_assets',
        'notes']
    list_filter = ['supplier__name']
    search_fields = [
        'supplier__name', 'supplier__account_rep', 'supplier__contact_email',
        'supplier__contact_phone', 'supplier__notes', 'supplier_ref', 'job_number',
        'total_value', 'notes']
