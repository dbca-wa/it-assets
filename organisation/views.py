from datetime import date
from django.http import HttpResponse
from django.views.generic import View
import xlsxwriter

from .models import DepartmentUser


class DepartmentUserExport(View):
    """A custom view to export details of active Department users to an Excel spreadsheet.
    """
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=department_users_{}.xlsx'.format(date.today().isoformat())

        with xlsxwriter.Workbook(
            response,
            {
                'in_memory': True,
                'default_date_format': 'dd-mmm-yyyy HH:MM',
                'remove_timezone': True,
            },
        ) as workbook:
            users = DepartmentUser.objects.filter(active=True)
            users_sheet = workbook.add_worksheet('Change requests')
            users_sheet.write_row('A1', (
                'COST CENTRE', 'NAME', 'EMAIL', 'ACCOUNT TYPE', 'POSITION TYPE', 'EXPIRY DATE'
            ))
            row = 1
            for i in users:
                users_sheet.write_row(row, 0, [
                    i.cost_centre.code if i.cost_centre else '', i.get_full_name(), i.email, i.get_account_type_display(),
                    i.get_position_type_display(), i.expiry_date if i.expiry_date else ''
                ])
                row += 1
            users_sheet.set_column('A:A', 13)
            users_sheet.set_column('B:B', 34)
            users_sheet.set_column('C:C', 46)
            users_sheet.set_column('D:D', 42)
            users_sheet.set_column('E:E', 13)
            users_sheet.set_column('F:F', 17)

        return response
