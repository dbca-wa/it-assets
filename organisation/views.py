from datetime import date, datetime

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.serializers import serialize
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.views.generic import ListView, View

from itassets.utils import get_next_pages, get_previous_pages

from .models import DepartmentUser, Location
from .reports import department_user_export, user_account_export


class AddressBook(LoginRequiredMixin, ListView):
    template_name = "organisation/address_book.html"
    model = DepartmentUser
    paginate_by = 50

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["site_title"] = "Office of Information Management"
        context["site_acronym"] = "OIM"
        context["page_title"] = "Address Book"
        # Pass in any query string.
        if "q" in self.request.GET:
            context["query_string"] = self.request.GET["q"]
        context["object_count"] = len(self.get_queryset())
        context["previous_pages"] = get_previous_pages(context["page_obj"])
        context["next_pages"] = get_next_pages(context["page_obj"])
        context["geoserver_url"] = settings.GEOSERVER_URL
        return context

    def get_queryset(self):
        queryset = (
            DepartmentUser.objects.filter(**DepartmentUser.ACTIVE_FILTER)
            .exclude(account_type__in=DepartmentUser.ACCOUNT_TYPE_EXCLUDE)
            .prefetch_related(
                "cost_centre",
            )
        )

        # Filter the queryset, if required.
        if "q" in self.request.GET and self.request.GET["q"]:
            query_str = self.request.GET["q"]
            queryset = queryset.filter(
                Q(name__icontains=query_str)
                | Q(title__icontains=query_str)
                | Q(telephone__icontains=query_str)
                | Q(mobile_phone__icontains=query_str)
                | Q(ascender_data__geo_location_desc__icontains=query_str)
                | Q(ascender_data__clevel5_desc__icontains=query_str)
            )

        queryset = queryset.order_by("name")

        return queryset


class UserAccounts(LoginRequiredMixin, ListView):
    """A custom view to return a subset of DepartmentUser objects having licensed AD accounts
    (though not necessarily enabled) as well as a 'current' job in Ascender (i.e. past its end date).
    """

    template_name = "organisation/user_accounts.html"
    model = DepartmentUser
    paginate_by = 50

    def get_queryset(self):
        queryset = (
            DepartmentUser.objects.filter(
                Q(assigned_licences__contains=["MICROSOFT 365 E5"])
                | Q(assigned_licences__contains=["MICROSOFT 365 F3"])
                | Q(assigned_licences__contains=["OFFICE 365 E5"])
                | Q(assigned_licences__contains=["OFFICE 365 E1"])
            )
            .prefetch_related(
                "cost_centre",
            )
            .order_by("name")
        )

        # Filter the queryset
        if "q" in self.request.GET and self.request.GET["q"]:
            query_str = self.request.GET["q"]
            queryset = queryset.filter(Q(name__icontains=query_str) | Q(cost_centre__code__icontains=query_str))

        # Last filter: Ascender job_end_date value is not in the past, or is absent.
        # We need to turn our queryset into a list comprehension to use the model property for filtering.
        queryset = [
            du
            for du in queryset
            if (
                (not du.get_job_end_date() or du.get_job_end_date() >= date.today())
                and (not du.get_job_start_date() or du.get_job_start_date() <= date.today())
            )
        ]

        return queryset

    def get(self, request, *args, **kwargs):
        # Return an Excel spreadsheet if requested.
        if "export" in self.request.GET and self.request.GET["export"]:
            response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = (
                f"attachment; filename=department_user_m365_licences_{date.today().isoformat()}_{datetime.now().strftime('%H%M')}.xlsx"
            )
            queryset = self.get_queryset()
            response = user_account_export(response, queryset)
            return response
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["site_title"] = "Office of Information Management"
        context["site_acronym"] = "OIM"
        context["page_title"] = "Department user Microsoft 365 licences"
        # Pass in any query string
        if "q" in self.request.GET:
            context["query_string"] = self.request.GET["q"]
        context["object_count"] = len(self.get_queryset())
        context["previous_pages"] = get_previous_pages(context["page_obj"])
        context["next_pages"] = get_next_pages(context["page_obj"])
        return context


class DepartmentUserAPIResource(View):
    """An API view that returns JSON of active department staff accounts."""

    def get(self, request, *args, **kwargs):
        queryset = (
            DepartmentUser.objects.filter(**DepartmentUser.ACTIVE_FILTER)
            .exclude(account_type__in=DepartmentUser.ACCOUNT_TYPE_EXCLUDE)
            .prefetch_related(
                "manager",
                "cost_centre",
                "location",
            )
            .order_by("name")
        )

        # Queryset filtering.
        if "pk" in kwargs and kwargs["pk"]:  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs["pk"])
        if "q" in self.request.GET:  # Allow basic filtering on email.
            queryset = queryset.filter(email__icontains=self.request.GET["q"])

        # Tailor the API response.
        if "selectlist" in request.GET:  # Smaller response, for use in HTML select lists.
            users = [{"id": user.pk, "text": user.email} for user in queryset]
        else:  # Normal API response.
            users = [
                {
                    "id": user.pk,
                    "name": user.name,
                    "given_name": user.given_name,
                    "surname": user.surname,
                    "preferred_name": user.preferred_name if user.preferred_name else None,
                    "email": user.email,
                    "title": user.title if user.title else None,
                    "telephone": user.telephone if user.telephone else None,
                    "extension": user.extension if user.extension else None,
                    "mobile_phone": user.mobile_phone if user.mobile_phone else None,
                    "location": {"id": user.location.pk, "name": user.location.name} if user.location else {},
                    "cost_centre": user.cost_centre.code if user.cost_centre else None,
                    "employee_id": user.employee_id
                    if user.employee_id
                    else None,  # NOTE: employee ID is used in the Moodle employee sync process.
                    "manager": {
                        "id": user.manager.pk,
                        "name": user.manager.name,
                        "email": user.manager.email,
                    }
                    if user.manager
                    else {},
                    "division": user.get_division(),
                    "unit": user.get_business_unit(),
                }
                for user in queryset
            ]

        return JsonResponse(users, safe=False)


class LocationAPIResource(View):
    """An API view that returns JSON of active physical locations."""

    def get(self, request, *args, **kwargs):
        queryset = Location.objects.filter(active=True).order_by("name")

        # Queryset filtering.
        if "pk" in kwargs and kwargs["pk"]:  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs["pk"])
        if "q" in self.request.GET:  # Allow basic filtering on name.
            queryset = queryset.filter(name__icontains=self.request.GET["q"])

        # Tailor the API response.
        if "selectlist" in request.GET:  # Smaller response, for use in HTML select lists.
            locations = [{"id": location.pk, "text": location.name} for location in queryset]
        elif "format" in request.GET and request.GET["format"] == "geojson":
            # Return the API response in GeoJSON format.
            locations = serialize(
                "geojson",
                Location.objects.filter(active=True, point__isnull=False, ascender_desc__isnull=False),
                geometry_field="point",
                srid=4283,
                fields=["id", "name", "address", "phone", "ascender_desc"],
            )
            return HttpResponse(content=locations, content_type="application/json")
        else:
            locations = [
                {
                    "id": location.pk,
                    "name": location.name,
                    "point": {"type": "Point", "coordinates": location.point.coords} if location.point else {},
                    "address": location.address,
                    "pobox": location.pobox,
                    "phone": location.phone,
                    "fax": location.fax,
                }
                for location in queryset
            ]

        return JsonResponse(locations, safe=False)


class LicenseAPIResource(View):
    """An API view that returns a list of active Microsoft-licensed accounts."""

    def get(self, request, *args, **kwargs):
        # Return active users having an E5 or E1 licence assigned.
        queryset = (
            DepartmentUser.objects.filter(
                active=True,
            )
            .filter(
                Q(assigned_licences__contains=["MICROSOFT 365 E5"])
                | Q(assigned_licences__contains=["MICROSOFT 365 F3"])
                | Q(assigned_licences__contains=["OFFICE 365 E5"])
                | Q(assigned_licences__contains=["OFFICE 365 E1"])
            )
            .prefetch_related(
                "cost_centre",
            )
            .order_by("name")
        )

        # Queryset filtering.
        if "pk" in kwargs and kwargs["pk"]:  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs["pk"])
        if "q" in self.request.GET:  # Allow basic filtering on email.
            queryset = queryset.filter(email__icontains=self.request.GET["q"])

        licenses = [
            {
                "id": user.pk,
                "name": user.name,
                "email": user.email,
                "cost_centre": user.cost_centre.code if user.cost_centre else None,
                "microsoft_365_licence": user.get_licence(),
                "active": user.active,
                "shared": user.shared_account,
            }
            for user in queryset
        ]

        return JsonResponse(licenses, safe=False)


class DepartmentUserExport(View):
    """A custom view to export details of active Department users to an Excel spreadsheet."""

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = (
            f"attachment; filename=department_users_{date.today().isoformat()}_{datetime.now().strftime('%H%M')}.xlsx"
        )

        if "all" in request.GET:  # Return all objects.
            users = DepartmentUser.objects.all()
        else:  # Default to active users only.
            users = DepartmentUser.objects.filter(**DepartmentUser.ACTIVE_FILTER).exclude(
                account_type__in=DepartmentUser.ACCOUNT_TYPE_EXCLUDE
            )

        response = department_user_export(response, users)
        return response
