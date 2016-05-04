from django.contrib.admin import AdminSite, ModelAdmin, register
from django.forms import ModelForm, ValidationError
from djqscsv import render_to_csv_response
import re
from reversion.admin import VersionAdmin

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


def export_location_assets(modeladmin, request, queryset):
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
