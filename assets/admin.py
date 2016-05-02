from django.contrib import admin
from django.forms import ModelForm, ValidationError
import re
from reversion.admin import VersionAdmin

from assets.models import Supplier, Model, Asset, Location, Invoice


class AuditAdmin(VersionAdmin, admin.ModelAdmin):
    list_display = ['__unicode__', 'creator', 'modifier', 'created', 'modified']
    search_fields = [
        'id', 'creator__username', 'modifier__username', 'creator__email',
        'modifier__email']
    raw_id_fields = ['creator', 'modifier']


class SupplierAdmin(AuditAdmin):
    list_display = ['name', 'get_account_rep', 'get_website', 'get_assets']
    search_fields = [
        'name', 'account_rep', 'contact_email', 'contact_phone', 'website', 'notes']
    actions_on_top = False
admin.site.register(Supplier, SupplierAdmin)


class AssetModelAdmin(AuditAdmin):
    list_display = ['manufacturer', 'model', 'model_type', 'get_assets', 'notes']
    list_filter = ['manufacturer']
    search_fields = ['manufacturer__name', 'model', 'notes', 'model_type']
    actions_on_top = False
    actions_selection_counter = False
admin.site.register(Model, AssetModelAdmin)


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


class AssetAdmin(AuditAdmin):
    list_display = [
        'asset_tag', 'get_type', 'get_model', 'serial', 'status', 'get_age',
        'get_location', 'get_assigned_user']
    list_filter = ['model__manufacturer', 'status', 'location__site', 'date_purchased']
    search_fields = [
        'asset_tag', 'model__model', 'status', 'model__manufacturer__name',
        'model__model_type', 'location__name', 'location__block', 'location__site',
        'assigned_user', 'serial', 'invoice__supplier_ref', 'invoice__job_number',
        'invoice__cost_centre_number', 'invoice__etj_number']
    form = AssetAdminForm

    # Cross-model lookups done in filters must be permitted here as
    # well for security reasons
    def lookup_allowed(self, key, value):
        return True
admin.site.register(Asset, AssetAdmin)


class LocationAdmin(AuditAdmin):
    list_display = ('name', 'block', 'site', 'get_assets')
    search_fields = ('name', 'block', 'site')
    actions_on_top = False
admin.site.register(Location, LocationAdmin)


class InvoiceAdmin(AuditAdmin):
    list_display = [
        'job_number', 'supplier', 'supplier_ref', 'total_value', 'get_assets',
        'notes']
    list_filter = ['supplier__name']
    search_fields = [
        'supplier__name', 'supplier__account_rep', 'supplier__contact_email',
        'supplier__contact_phone', 'supplier__notes', 'supplier_ref', 'job_number',
        'total_value', 'notes']
    actions_on_top = False

    # Cross-model lookups done in the filter above must be permitted here as
    # well for security reasons
    def lookup_allowed(self, key, value):
        return True

admin.site.register(Invoice, InvoiceAdmin)
