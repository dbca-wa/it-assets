from datetime import date, datetime
from django.http import HttpResponse
from django.views.generic import View
import xlsxwriter

from django.views.generic import View, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from registers.utils import search_filter
from django.core.paginator import Paginator

from .models import HardwareAsset


class HardwareAssetExport(View):
    """A custom view to export details of non-disposed hardware assets to an Excel spreadsheet.
    """
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=hardware_assets_{}.xlsx'.format(date.today().isoformat())

        with xlsxwriter.Workbook(
            response,
            {
                'in_memory': True,
                'default_date_format': 'dd-mmm-yyyy HH:MM',
                'remove_timezone': True,
            },
        ) as workbook:
            money = workbook.add_format({'num_format': '$#,##0.00;-$#,##0.00'})
            assets = HardwareAsset.objects.filter(status__in=['In storage', 'Deployed'])
            assets_sheet = workbook.add_worksheet('Hardware assets')
            assets_sheet.write_row('A1', (
                'ASSET TAG', 'FINANCE ASSET TAG', 'SERIAL', 'VENDOR', 'MODEL TYPE', 'HARDWARE MODEL',
                'STATUS', 'COST CENTRE', 'LOCATION', 'ASSIGNED USER', 'DATE PURCHASED',
                'PURCHASED VALUE', 'SERVICE REQUEST URL', 'LOCAL PROPERTY', 'IS ASSET', 'WARRANTY END',
            ))
            row = 1
            for i in assets:
                assets_sheet.write_row(row, 0, [
                    i.asset_tag, i.finance_asset_tag, i.serial, i.vendor.name,
                    i.hardware_model.get_model_type_display(), i.hardware_model.model_no, i.get_status_display(),
                    i.cost_centre.code if i.cost_centre else '', i.location.name if i.location else '',
                    i.assigned_user.get_full_name() if i.assigned_user else '',
                    datetime.strftime(i.date_purchased, '%d/%b/%Y') if i.date_purchased else '',
                    i.purchased_value, i.service_request_url, i.local_property, i.is_asset,
                    datetime.strftime(i.warranty_end, '%d/%b/%Y') if i.warranty_end else '',
                ])
                row += 1
            assets_sheet.set_column('A:A', 11)
            assets_sheet.set_column('B:B', 19)
            assets_sheet.set_column('C:C', 22)
            assets_sheet.set_column('D:D', 26)
            assets_sheet.set_column('E:E', 28)
            assets_sheet.set_column('F:F', 35)
            assets_sheet.set_column('G:G', 10)
            assets_sheet.set_column('H:H', 13)
            assets_sheet.set_column('I:I', 34)
            assets_sheet.set_column('J:J', 22)
            assets_sheet.set_column('K:K', 16)
            assets_sheet.set_column('L:L', 18, money)
            assets_sheet.set_column('M:M', 30)
            assets_sheet.set_column('N:N', 15)
            assets_sheet.set_column('O:O', 8)
            assets_sheet.set_column('P:P', 15)

        return response

class HardwareAssetList(LoginRequiredMixin, ListView):
    model = HardwareAsset
    paginate_by = 50


    def get_queryset(self):
        from .admin import HardwareAssetAdmin
        queryset = super(HardwareAssetList, self).get_queryset()
        # if 'mine' in self.request.GET:
        #     email = self.request.user.email
        #     queryset = queryset.filter(requester__email__iexact=email)
        if 'q' in self.request.GET and self.request.GET['q']:
            q = search_filter(HardwareAssetAdmin.search_fields, self.request.GET['q'])
            queryset = queryset.filter(q)
        return queryset

    def get_context_data(self, **kwargs):
        context = super(HardwareAssetList, self).get_context_data(**kwargs)
        # Pass in any query string
        if 'q' in self.request.GET:
            context['query_string'] = self.request.GET['q']
        return context

class HardwareAssetDetail(LoginRequiredMixin, DetailView):
    model = HardwareAsset

    def get_context_data(self, **kwargs):
        context = super(HardwareAssetDetail, self).get_context_data(**kwargs)
        return context



