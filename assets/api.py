from django.conf.urls import url
from django.http import HttpResponse
from django.views import View
from restless.dj import DjangoResource
from restless.preparers import Preparer
from restless.resources import skip_prepare

from .utils import get_csv
from .models import HardwareAsset


class HardwareAssetPreparer(Preparer):
    """Custom field preparer class for HardwareAssetResource.
    """
    def prepare(self, data):
        result = {
            'asset_tag': data.asset_tag,
            'finance_asset_tag': data.finance_asset_tag,
            'serial': data.serial,
            'vendor': data.vendor.name,
            'hardware_model': data.hardware_model.model_type,
            'status': data.get_status_display(),
            'notes': data.notes,
            'cost_centre': data.cost_centre.name if data.cost_centre else '',
            'location': data.location.name if data.location else '',
            'assigned_user': data.assigned_user.email if data.assigned_user else '',
            'date_purchased': data.date_purchased,
            'purchased_value': data.purchased_value,
            'is_asset': data.is_asset,
            'local_property': data.local_property,
            'warranty_end': data.warranty_end
        }
        return result


class HardwareAssetResource(DjangoResource):
    VALUES_ARGS = ('asset_tag', 'status', 'org_unit__name', 'cost_centre__code')
    preparer = HardwareAssetPreparer()

    def __init__(self, *args, **kwargs):
        super(HardwareAssetResource, self).__init__(*args, **kwargs)
        self.http_methods.update({
            'detail_tag': {'GET': 'detail_tag'},
            'get_csv': {'GET': 'get_csv'},
        })

    @classmethod
    def urls(self, name_prefix=None):
        urlpatterns = super(HardwareAssetResource, self).urls(name_prefix=name_prefix)
        return [
            url(r'^(?P<asset_tag>[Ii][Tt][0-9]+)/$', self.as_view('detail_tag'), name=self.build_url_name('detail_tag', name_prefix)),
        ] + urlpatterns

    def list_qs(self):
        # By default, filter out 'Disposed' assets.
        filters = {'status__in': ['In storage', 'Deployed']}
        if 'all' in self.request.GET:
            filters.pop('status__in')
        if 'asset_tag' in self.request.GET:
            filters.pop('status__in')  # Also search disposed assets.
            filters['asset_tag__icontains'] = self.request.GET['asset_tag']
        if 'cost_centre' in self.request.GET:
            filters['cost_centre__code__icontains'] = self.request.GET['cost_centre']
        return HardwareAsset.objects.filter(**filters).prefetch_related(
            'vendor', 'hardware_model', 'cost_centre', 'location', 'assigned_user'
        )

    def list(self):
        return list(self.list_qs())

    def detail(self, pk):
        return HardwareAsset.objects.get(pk=pk)

    @skip_prepare
    def detail_tag(self, asset_tag):
        """Custom endpoint to return a single hardware asset, filterd by asset tag no.
        """
        return self.prepare(HardwareAsset.objects.get(asset_tag__istartswith=asset_tag))


class HardwareAssetCSV(View):
    """Custom view to return filtered hardware assets as CSV, because I am too dumb
    to work out how to accomplish this within restless :|
    """

    def get(self, request, *args, **kwargs):
        filters = {'status__in': ['In storage', 'Deployed']}
        if 'all' in self.request.GET:
            filters.pop('status__in')
        if 'asset_tag' in self.request.GET:
            filters.pop('status__in')  # Also search disposed assets.
            filters['asset_tag__icontains'] = self.request.GET['asset_tag']
        if 'cost_centre' in self.request.GET:
            filters['cost_centre__code__icontains'] = self.request.GET['cost_centre']
        qs = HardwareAsset.objects.filter(**filters).prefetch_related(
            'vendor', 'hardware_model', 'cost_centre', 'location', 'assigned_user'
        )
        f = get_csv(qs)
        response = HttpResponse(f.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=hardwareasset_export.csv'
        return response
