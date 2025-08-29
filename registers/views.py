from django.db.models import Q
from django.http import JsonResponse
from django.views.generic import View

from .models import ITSystem


class ITSystemAPIResource(View):
    """An API view that returns JSON of current IT Systems."""

    def get(self, request, *args, **kwargs):
        queryset = ITSystem.objects.filter(
            status__in=[0, 2],
        ).prefetch_related(
            "cost_centre",
            "owner",
            "technology_custodian",
            "information_custodian",
        )

        # Queryset filtering.
        if "pk" in kwargs and kwargs["pk"]:  # Allow filtering by object PK.
            queryset = queryset.filter(pk=kwargs["pk"])
        if "q" in self.request.GET:  # Allow basic filtering on name or system ID
            queryset = queryset.filter(Q(name__icontains=self.request.GET["q"]) | Q(system_id=self.request.GET["q"]))

        # Tailor the API response.
        if "selectlist" in request.GET:  # Smaller response, for use in HTML select lists.
            systems = [{"id": system.pk, "text": system.name} for system in queryset]
        else:  # Normal API response.
            systems = [
                {
                    "id": system.pk,
                    "name": system.name,
                    "system_id": system.system_id,
                    "status": system.get_status_display(),
                    "link": system.link,
                    "description": system.description,
                    "cost_centre": system.cost_centre.code if system.cost_centre else None,
                    "owner": system.owner.name if system.owner else None,
                    "technology_custodian": system.technology_custodian.name if system.technology_custodian else None,
                    "information_custodian": system.information_custodian.name if system.information_custodian else None,
                    "availability": system.get_availability_display() if system.availability else None,
                    "seasonality": system.get_seasonality_display() if system.seasonality else None,
                }
                for system in queryset
            ]

        return JsonResponse(systems, safe=False)
