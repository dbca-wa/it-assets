from datetime import date, datetime
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, JsonResponse
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import View, ListView, DetailView, UpdateView, FormView, TemplateView
from django.views.decorators.clickjacking import xframe_options_exempt
from csp.decorators import csp_exempt
from itassets.utils import breadcrumbs_list

from .forms import ConfirmPhoneNosForm
from .models import DepartmentUser, Location, OrgUnit, ADAction
from .reports import department_user_export, user_account_export, department_user_ascender_discrepancies
from .utils import parse_windows_ts

decorators = [xframe_options_exempt, csp_exempt]


@method_decorator(decorators, name='dispatch')
class AddressBook(TemplateView):
    template_name = 'organisation/address_book.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_title'] = 'Office of Information Management'
        context['site_acronym'] = 'OIM'
        context['page_title'] = 'Address Book'
        return context


class UserAccounts(LoginRequiredMixin, ListView):
    template_name = 'organisation/user_accounts.html'
    model = DepartmentUser
    paginate_by = 50

    def get_queryset(self):
        queryset = DepartmentUser.objects.filter(
            Q(assigned_licences__contains=['MICROSOFT 365 E5']) |
            Q(assigned_licences__contains=['MICROSOFT 365 F3']) |
            Q(assigned_licences__contains=['OFFICE 365 E5']) |
            Q(assigned_licences__contains=['OFFICE 365 E1'])
        ).prefetch_related(
            'cost_centre',
        ).order_by('name')

        # Filter the queryset
        if "q" in self.request.GET and self.request.GET["q"]:
            query_str = self.request.GET["q"]
            queryset = queryset.filter(
                Q(name__icontains=query_str) |
                Q(cost_centre__code__icontains=query_str)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_title'] = 'Office of Information Management'
        context['site_acronym'] = 'OIM'
        context['page_title'] = 'Department user Microsoft 365 licences'
        # Pass in any query string
        if "q" in self.request.GET:
            context["query_string"] = self.request.GET["q"]
        return context


class UserAccountsExport(View):
    """A custom view to return a subset of "active" DepartmentUser data to an Excel spreadsheet.
    """
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=department_user_m365_licences_{}_{}.xlsx'.format(date.today().isoformat(), datetime.now().strftime('%H%M'))

        # TODO: filtering via request params.
        queryset = DepartmentUser.objects.filter(
            Q(assigned_licences__contains=['MICROSOFT 365 E5']) |
            Q(assigned_licences__contains=['MICROSOFT 365 F3']) |
            Q(assigned_licences__contains=['OFFICE 365 E5']) |
            Q(assigned_licences__contains=['OFFICE 365 E1'])
        ).order_by('name')
        if "q" in self.request.GET and self.request.GET["q"]:
            query_str = self.request.GET["q"]
            queryset = queryset.filter(
                Q(name__icontains=query_str) |
                Q(cost_centre__code__icontains=query_str)
            )
        response = user_account_export(response, queryset)
        return response


class DepartmentUserAPIResource(View):
    """An API view that returns JSON of active department staff accounts.
    """
    def get(self, request, *args, **kwargs):
        queryset = DepartmentUser.objects.filter(
            **DepartmentUser.ACTIVE_FILTER
        ).exclude(
            account_type__in=DepartmentUser.ACCOUNT_TYPE_EXCLUDE
        ).prefetch_related(
            'manager',
            'cost_centre',
            'location',
            'org_unit',
        ).order_by('name')

        # Queryset filtering.
        if 'pk' in kwargs and kwargs['pk']:  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs['pk'])
        if 'q' in self.request.GET:  # Allow basic filtering on email.
            queryset = queryset.filter(email__icontains=self.request.GET['q'])

        # Tailor the API response.
        if 'selectlist' in request.GET:  # Smaller response, for use in HTML select lists.
            users = [{'id': user.pk, 'text': user.email} for user in queryset]
        else:  # Normal API response.
            users = [
                {
                    'id': user.pk,
                    'name': user.name,
                    'given_name': user.given_name,
                    'surname': user.surname,
                    'preferred_name': user.preferred_name if user.preferred_name else None,
                    'email': user.email,
                    'title': user.title if user.title else None,
                    'telephone': user.telephone if user.telephone else None,
                    'extension': user.extension if user.extension else None,
                    'mobile_phone': user.mobile_phone if user.mobile_phone else None,
                    'location': {'id': user.location.pk, 'name': user.location.name} if user.location else {},
                    'org_unit': {'id': user.org_unit.pk, 'name': user.org_unit.name, 'acronym': user.org_unit.acronym} if user.org_unit else {},
                    'group_unit': {'id': user.group_unit.pk, 'name': user.group_unit.name, 'acronym': user.group_unit.acronym} if user.group_unit else {},
                    'cost_centre': user.cost_centre.code if user.cost_centre else None,
                    'employee_id': user.employee_id if user.employee_id else None,  # NOTE: employee ID is used in the Moodle employee sync process.
                    'manager': {'id': user.manager.pk, 'name': user.manager.name, 'email': user.manager.email} if user.manager else {},
                } for user in queryset
            ]

        return JsonResponse(users, safe=False)


class LocationAPIResource(View):
    """An API view that returns JSON of active physical locations.
    """
    def get(self, request, *args, **kwargs):
        queryset = Location.objects.filter(active=True).order_by('name')

        # Queryset filtering.
        if 'pk' in kwargs and kwargs['pk']:  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs['pk'])
        if 'q' in self.request.GET:  # Allow basic filtering on name.
            queryset = queryset.filter(name__icontains=self.request.GET['q'])

        # Tailor the API response.
        if 'selectlist' in request.GET:  # Smaller response, for use in HTML select lists.
            locations = [{'id': location.pk, 'text': location.name} for location in queryset]
        else:
            locations = [
                {
                    'id': location.pk,
                    'name': location.name,
                    'point': {'type': 'Point', 'coordinates': location.point.coords} if location.point else {},
                    'address': location.address,
                    'pobox': location.pobox,
                    'phone': location.phone,
                    'fax': location.fax,
                } for location in queryset
            ]

        return JsonResponse(locations, safe=False)


class OrgUnitAPIResource(View):
    """An API view that returns JSON of active organisation units.
    """
    def get(self, request, *args, **kwargs):
        queryset = OrgUnit.objects.filter(active=True).order_by('name')

        # Queryset filtering.
        if 'pk' in kwargs and kwargs['pk']:  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs['pk'])
        if 'q' in self.request.GET:  # Allow basic filtering on name.
            queryset = queryset.filter(name__icontains=self.request.GET['q'])
        if 'division' in self.request.GET:  # Allow filtering to divisions only.
            queryset = queryset.filter(unit_type=1)
        if 'division_id' in self.request.GET and self.request.GET['division_id']:  # Allow filtering to org units belonging to a division.
            queryset = queryset.filter(division_unit__pk=self.request.GET['division_id'])

        # Tailor the API response.
        if 'selectlist' in request.GET:  # Smaller response, for use in HTML select lists.
            org_units = [{'id': ou.pk, 'text': ou.name} for ou in queryset]
        else:
            org_units = [
                {
                    'id': ou.pk,
                    'name': ou.name,
                    'division_id': ou.division_unit.pk if ou.division_unit else None,
                } for ou in queryset
            ]

        return JsonResponse(org_units, safe=False)


class LicenseAPIResource(View):
    """An API view that returns a list of active Microsoft-licensed accounts.
    """

    def get(self, request, *args, **kwargs):
        # Return active users having an E5 or E1 licence assigned.
        queryset = DepartmentUser.objects.filter(
            active=True,
        ).filter(
            Q(assigned_licences__contains=['MICROSOFT 365 E5']) |
            Q(assigned_licences__contains=['MICROSOFT 365 F3']) |
            Q(assigned_licences__contains=['OFFICE 365 E5']) |
            Q(assigned_licences__contains=['OFFICE 365 E1'])
        ).prefetch_related(
            'cost_centre',
        ).order_by('name')

        # Queryset filtering.
        if 'pk' in kwargs and kwargs['pk']:  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs['pk'])
        if 'q' in self.request.GET:  # Allow basic filtering on email.
            queryset = queryset.filter(email__icontains=self.request.GET['q'])

        licenses = [
            {
                'id': user.pk,
                'name': user.name,
                'email': user.email,
                'cost_centre': user.cost_centre.code if user.cost_centre else None,
                'microsoft_365_licence': user.get_licence(),
                'active': user.active,
                'shared': user.shared_account,
            } for user in queryset
        ]

        return JsonResponse(licenses, safe=False)


class DepartmentUserExport(View):
    """A custom view to export details of active Department users to an Excel spreadsheet.
    """
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=department_users_{}_{}.xlsx'.format(date.today().isoformat(), datetime.now().strftime('%H%M'))

        if 'all' in request.GET:  # Return all objects.
            users = DepartmentUser.objects.all()
        else:  # Default to active users only.
            users = DepartmentUser.objects.filter(**DepartmentUser.ACTIVE_FILTER).exclude(account_type__in=DepartmentUser.ACCOUNT_TYPE_EXCLUDE)

        response = department_user_export(response, users)
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
        context['site_title'] = 'DBCA Office of Information Management'
        context['site_acronym'] = 'OIM'
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
        context['site_title'] = 'DBCA Office of Information Management'
        context['site_acronym'] = 'OIM'
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
        # We should already have checked permissions in dispatch, so 'complete' the ADAction.
        action = self.get_object()
        action.completed = timezone.localtime()
        action.completed_by = request.user
        action.save()
        messages.success(request, "Action {} has been marked as marked as completed".format(action.pk))
        return HttpResponseRedirect(reverse("ad_action_list"))


class DepartmentUserAscenderDiscrepancyExport(View):
    """A custom view to export discrepancies between Ascender and department user data to an Excel spreadsheet.
    """
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=ascender_ad_discrepancies_{}_{}.xlsx'.format(date.today().isoformat(), datetime.now().strftime('%H%M'))
        users = DepartmentUser.objects.all()
        response = department_user_ascender_discrepancies(response, users)
        return response
