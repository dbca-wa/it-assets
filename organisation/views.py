from datetime import date, datetime
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden
from django.urls import reverse
from django.views.generic import View, ListView, DetailView, UpdateView
from itassets.utils import breadcrumbs_list

from .models import DepartmentUser, ADAction
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


class ADActionList(LoginRequiredMixin, ListView):
    model = ADAction

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(completed__isnull=True).order_by('created')

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or (request.user.is_staff and Group.objects.get(name='OIM Staff') in request.user.groups.all())):
            return HttpResponseForbidden('Unauthorised')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Active Directory actions'
        # Breadcrumb links:
        links = [(None, 'AD actions')]
        context["breadcrumb_trail"] = breadcrumbs_list(links)
        return context


class ADActionDetail(LoginRequiredMixin, DetailView):
    model = ADAction

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or (request.user.is_staff and Group.objects.get(name='OIM Staff') in request.user.groups.all())):
            return HttpResponseForbidden('Unauthorised')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context['page_title'] = 'Active Directory action {}'.format(obj.pk)
        # Breadcrumb links:
        links = [(reverse("ad_action_list"), "AD actions"), (None, obj.pk)]
        context["breadcrumb_trail"] = breadcrumbs_list(links)
        return context


class ADActionComplete(LoginRequiredMixin, UpdateView):
    model = ADAction

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or (request.user.is_staff and Group.objects.get(name='OIM Staff') in request.user.groups.all())):
            return HttpResponseForbidden('Unauthorised')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        # We should already have check permissions in dispatch, so 'complete' the ADAction.
        action = self.get_object()
        action.completed = datetime.now()
        action.completed_by = request.user
        action.save()
        messages.success(request, "Action {} has been marked as marked as completed".format(action.pk))
        return HttpResponseRedirect(reverse("ad_action_list"))
