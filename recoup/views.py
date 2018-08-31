from django.views.generic.base import TemplateView
from django.http import HttpResponse
from django.utils import timezone
from decimal import Decimal
import xlsxwriter

from recoup import models


class RecoupSummaryView(TemplateView):
    template_name = 'recoup/summary.html'
    title = 'IT Recoup Cost DB'

    def get_context_data(self, **kwargs):
        context = super(RecoupSummaryView, self).get_context_data(**kwargs)
        context['site_header'], context['site_title'] = self.title, self.title
        context['year'] = models.FinancialYear.objects.first()
        context['enduser_cost'] = round(sum([e.cost_estimate() for e in models.EndUserService.objects.all()]), 2)
        context['platform_cost'] = round(sum([p.cost_estimate() for p in models.ITPlatform.objects.all()]), 2)
        context['unallocated_cost'] = context['year'].cost_estimate() - context['enduser_cost'] - context['platform_cost']
        return context


class BillView(TemplateView):
    template_name = 'recoup/bill.html'

    def get_context_data(self, **kwargs):
        context = super(BillView, self).get_context_data(**kwargs)
        division = models.Division.objects.get(pk=int(self.request.GET['division']))
        services = division.enduserservice_set.all()

        for service in services:
            service.cost_estimate_display = round(Decimal(division.user_count) / Decimal(service.total_user_count()) * service.cost_estimate(), 2)
        context.update({
            'division': division,
            'services': services,
            'created': timezone.now().date
        })
        return context


def DUCReport(request):
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=DUCReport.xlsx'

    with xlsxwriter.Workbook(response, {'in_memory': True}) as workbook:
        bold = workbook.add_format({'bold': True})
        bold_big_font = workbook.add_format({'bold': True, 'align': 'center'})
        bold_big_font.set_font_size(14)
        bold_italic = workbook.add_format({'bold': True, 'italic': True})
        pct = workbook.add_format({'num_format': '0.00%'})
        pct_bold = workbook.add_format({'num_format': '0.00%', 'bold': True})
        pct_bold_italic = workbook.add_format({'num_format': '0.00%', 'bold': True, 'italic': True})
        money = workbook.add_format({'num_format': '#,##0.00'})
        money_bold = workbook.add_format({'num_format': '#,##0.00', 'bold': True})
        money_bold_italic = workbook.add_format({'num_format': '#,##0.00', 'bold': True, 'italic': True})

        # Statement worksheet
        invoice = workbook.add_worksheet('Statement')
        invoice.write_row('A1', (
            'Division / Cost Centre', 'Computer User Accounts', 'End User Services ($)',
            'Business IT Systems ($)', 'Total DUC Estimated Cost ($)'))
        invoice.set_row(0, None, bold_big_font)
        user_count = 0
        for division in models.Division.objects.all():
            user_count += division.user_count
        enduser_total = 0
        for service in models.EndUserService.objects.all():
            enduser_total += service.cost_estimate()
        platform_cost = round(sum([p.cost_estimate() for p in models.ITPlatform.objects.all()]), 2)
        # Insert total row at the top
        invoice.write('A2', 'Total', bold_italic)
        invoice.write('B2', user_count, bold_italic)
        invoice.write('C2', enduser_total, money_bold_italic)
        invoice.write('D2', platform_cost, money_bold_italic)
        invoice.write('E2', enduser_total + platform_cost, money_bold_italic)
        row = 2
        divrow = 2
        for division in models.Division.objects.all():
            invoice.write(row, 0, division.org_unit.name, bold)
            invoice.write(row, 1, division.user_count, bold)
            invoice.write(row, 2, division.enduser_estimate(), money_bold)
            invoice.write(row, 3, division.system_cost_estimate(), money_bold)
            invoice.write(row, 4, division.enduser_estimate() + division.system_cost_estimate(), money_bold)
            divrow = row
            row += 1
            for cc in division.costcentrelink_set.all():
                invoice.write_row(row, 0, [
                    cc.cc.name, cc.user_count, '=B{}*C{}/B{}'.format(row + 1, divrow + 1, divrow + 1),
                    cc.system_cost_estimate(), '=SUM(C{},D{})'.format(row + 1, row + 1)])
                row += 1
        invoice.set_column('A:A', 34)
        invoice.set_column('B:B', 28)
        invoice.set_column('C:D', 27, money)
        invoice.set_column('E:E', 33, money)

        # Computer user account worksheet
        staff = workbook.add_worksheet('User Accounts')
        staff.write_row('A1', ('Division / Cost Centre', 'Computer User Accounts', '% Total'))
        staff.set_row(0, None, bold_big_font)
        row = 2
        for division in models.Division.objects.all():
            staff.write(row, 0, division.org_unit.name, bold)
            staff.write(row, 1, division.user_count, bold)
            staff.write(row, 2, division.user_count_percentage() / 100, pct_bold)
            row += 1
            for cc in division.costcentrelink_set.all():
                staff.write_row(row, 0, [cc.cc.name, cc.user_count, cc.user_count_percentage() / 100])
                row += 1
        staff.set_column('A:A', 35)
        staff.set_column('B:B', 30)
        staff.set_column('C:C', 10, pct)
        # Insert total row at the top
        staff.write('A2', 'Total', bold_italic)
        staff.write('B2', user_count, bold_italic)
        staff.write('C2', 1, pct_bold_italic)

        # End User services worksheet
        enduser = workbook.add_worksheet('End-User Services')
        enduser.write_row('A1', ('End-User Services', 'Estimated Cost ($)'))
        enduser.set_row(0, None, bold_big_font)
        row = 2
        for service in models.EndUserService.objects.all():
            enduser.write_row(row, 0, [service.name, service.cost_estimate()])
            row += 1
        enduser.set_column('A:A', 40)
        enduser.set_column('B:B', 22, money)
        # Insert total row at the top
        enduser.write('A2', 'Total', bold_italic)
        enduser.write('B2', enduser_total, money_bold_italic)

        # Business IT systems worksheet
        itsystems = workbook.add_worksheet('Business IT Systems')
        itsystems.write_row('A1', ('Division / Cost Centre', 'Business IT Systems', 'Estimated Cost ($)', '% Total'))
        itsystems.set_row(0, None, bold_big_font)
        # Insert total row at the top
        itsystems.write('A2', 'Total', bold_italic)
        itsystems.write('B2', 'All IT Systems', bold_italic)
        itsystems.write('C2', platform_cost, money_bold_italic)
        itsystems.write('D2', 1, pct_bold_italic)
        row = 2
        for division in models.Division.objects.all():
            itsystems.write(row, 0, division.org_unit.name, bold)
            itsystems.write(row, 1, 'Subtotal', bold)
            itsystems.write(row, 2, division.system_cost_estimate(), money_bold)
            itsystems.write(row, 3, '=C{}/C2'.format(row + 1), pct_bold)
            row += 1
            for system in division.divisionitsystem_set.filter(depends_on__isnull=False).distinct():
                itsystems.write_row(row, 0, [system.cost_centre.cc.name, system.__str__(), system.cost_estimate(), '=C{}/C2'.format(row + 1)])
                row += 1
        itsystems.set_column('A:A', 35)
        itsystems.set_column('B:B', 68)
        itsystems.set_column('C:C', 22, money)
        itsystems.set_column('D:D', 10, pct)

        # Bill worksheet
        bills = workbook.add_worksheet('Bills')
        bills.write_row('A1', (
            'Brand', 'Vendor', 'Description', 'Contract Reference', 'Quantity', 'Renewal Date',
            'Estimated Cost ($)', 'Comment'))
        bills.set_row(0, None, bold_big_font)
        row = 1
        for bill in models.Bill.objects.filter(active=True, cost_estimate__gt=0).order_by('contract__brand', 'contract__vendor', 'name'):
            bills.write(row, 0, bill.contract.brand)
            bills.write(row, 1, bill.contract.vendor)
            bills.write(row, 2, bill.name)
            bills.write(row, 3, bill.contract.reference)
            bills.write(row, 4, bill.quantity)
            if bill.renewal_date:
                renewal_date = bill.renewal_date.isoformat()
            else:
                renewal_date = 'N/A'
            bills.write(row, 5, renewal_date)
            bills.write(row, 6, bill.cost_estimate)
            bills.write(row, 7, bill.comment)
            row += 1
        bills.set_column('A:B', 22)
        bills.set_column('C:C', 78)
        bills.set_column('D:D', 36)
        bills.set_column('E:E', 10)
        bills.set_column('F:F', 16)
        bills.set_column('G:G', 20, money)
        bills.set_column('H:H', 60)

        # Cost Breakdown worksheet
        costs = workbook.add_worksheet('Cost Breakdown')
        costs.write_row('A1', (
            'Category', 'Type', 'Brand', 'Vendor', 'Contract Reference', 'Description (1)',
            'Description (2)', 'Service Pool', 'Percentage', 'Estimate Cost ($)'))
        costs.set_row(0, None, bold_big_font)
        row = 1
        for cost in models.EndUserCost.objects.order_by('service__name', 'bill__contract__brand', 'bill__contract__vendor', 'bill__name'):
            costs.write(row, 0, 'End-User Services'),
            costs.write(row, 1, cost.service.name),
            costs.write(row, 2, cost.bill.contract.brand),
            costs.write(row, 3, cost.bill.contract.vendor)
            costs.write(row, 4, cost.bill.contract.reference)
            costs.write(row, 5, cost.name)
            costs.write(row, 6, cost.bill.name)
            costs.write(row, 7, cost.service_pool.name)
            costs.write(row, 8, cost.percentage / 100)
            costs.write(row, 9, cost.cost_estimate)
            row += 1
        for cost in models.ITPlatformCost.objects.order_by('platform__name', 'bill__contract__brand', 'bill__contract__vendor', 'bill__name'):
            costs.write(row, 0, 'IT Platform'),
            costs.write(row, 1, cost.platform.name),
            costs.write(row, 2, cost.bill.contract.brand),
            costs.write(row, 3, cost.bill.contract.vendor)
            costs.write(row, 4, cost.bill.contract.reference)
            costs.write(row, 5, cost.name)
            costs.write(row, 6, cost.bill.name)
            costs.write(row, 7, cost.service_pool.name)
            costs.write(row, 8, cost.percentage / 100)
            costs.write(row, 9, cost.cost_estimate)
            row += 1
        costs.set_column('A:A', 20)
        costs.set_column('B:B', 28)
        costs.set_column('C:D', 22)
        costs.set_column('E:G', 30)
        costs.set_column('H:H', 17)
        costs.set_column('I:I', 17, pct)
        costs.set_column('J:J', 20, money)

    return response
