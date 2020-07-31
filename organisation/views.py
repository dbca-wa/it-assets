from datetime import date, datetime
from django.http import HttpResponse
from django.views.generic import View

from .models import DepartmentUser
from .reports import department_user_export, departmentuser_alesco_descrepancy, user_account_export


class DepartmentUserExport(View):
    """A custom view to export details of active Department users to an Excel spreadsheet.
    """
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=department_users_{}_{}.xlsx'.format(date.today().isoformat(), datetime.now().strftime('%H%M'))

        if 'all' in request.GET:  # Return all objects.
            users = DepartmentUser.objects.all()
        else:  # Default to active users only.
            users = DepartmentUser.objects.filter(active=True)

        response = department_user_export(response, users)
        return response


class DepartmentUserDiscrepancyReport(View):
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=departmentuser_alesco_discrepancies_{}_{}.xlsx'.format(date.today().isoformat(), datetime.now().strftime('%H%M'))

        if 'all' in request.GET:  # Return all objects with an Employee ID.
            users = DepartmentUser.objects.filter(employee_id__isnull=False)
        else:  # Default to active users only.
            users = DepartmentUser.objects.filter(active=True, employee_id__isnull=False)

        response = departmentuser_alesco_descrepancy(response, users)
        return response


class UserAccountExport(View):
    """A custom view to return a subset of DepartmentUser data to an Excel spreadsheet,
    being active accounts that consume an O365 licence and haven't been deleted from AD.
    """
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=user_accounts_{}_{}.xlsx'.format(date.today().isoformat(), datetime.now().strftime('%H%M'))

        # TODO: filtering via request params.
        users = DepartmentUser.objects.filter(active=True, o365_licence=True).order_by('username')
        response = user_account_export(response, users)
        return response
