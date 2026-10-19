from django.views.generic import View
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control
from django.conf import settings
from django.http import JsonResponse  # , HttpResponse

from assets.models import Asset, AssetTag
# from assets.exports import export_vulns

# from datetime import date, datetime

# class VulnerabilityExport(View):
#     """A custom view to export details of an asset's vulerabilities as a csv."""

#     def get(self, request, *args, **kwargs):
#         response = HttpResponse(content_type="text/csv")
#         response["Content-Disposition"] = (
#             f"attachment; filename=asset_vulns_{date.today().isoformat()}_{datetime.now().strftime('%H%M')}.csv"
#         )

#         if "assets" in request.GET:  # Only return vulns from the asset list
#             assets = Asset.objects.filter(tenable_id__in=request.GET["assets"])
#         else:  # Return all assets vulns
#             assets = Asset.objects.all()

#         return export_vulns(response=response, assets=assets)


class AssetAPIResource(View):
    """An API view that returns JSON of assets."""

    @method_decorator(cache_control(max_age=settings.API_RESPONSE_CACHE_SECONDS, private=True))
    def get(self, request, *args, **kwargs) -> JsonResponse:
        """
        Returns a json object recorded assets.
        Provides filtering functionality on ID, name, os, tag catgory, tag value.
        Has an additional flag of "show_tenable_data" that will modify the response to contain the raw tenable data used to generate the asset.
        """
        queryset = Asset.objects.all().order_by("name")

        # Queryset filtering.
        # By ID
        if "pk" in kwargs and kwargs["pk"]:
            queryset = queryset.filter(pk=kwargs["pk"])
        # By name
        if "name" in self.request.GET:
            queryset = queryset.filter(name__icontains=self.request.GET["name"])
        # By OS
        if "os" in self.request.GET:
            queryset = queryset.filter(os__icontains=self.request.GET["os"])
        # By tag - case insensistive exact instead of os & name's "contains"
        if "tag_cat" in self.request.GET and "tag" in self.request.GET:  # By tag within a specific category
            found_tag = AssetTag.objects.filter(category__name__iexact=self.request.GET["tag_cat"], name__iexact=self.request.GET["tag"])
            if found_tag.exists():
                queryset = queryset.filter(tags=found_tag.first())
            else:
                queryset = []
        elif "tag_cat" in self.request.GET:  # By any tag inside a tag category
            queryset = queryset.filter(tags__category__name__iexact=self.request.GET["tag_cat"])
        elif "tag" in self.request.GET:  # By a tag across any tag category
            queryset = queryset.filter(tags__name__iexact=self.request.GET["tag"])

        if "show_tenable_data" in self.request.GET:
            assets = [
                {
                    "id": asset.pk,
                    "name": asset.name,
                    "aliases": asset.aliases,
                    "description": asset.description,
                    "contacts": asset.asset_contacts,
                    "systems": asset.associated_systems,
                    "os": asset.os,
                    "os_version": asset.os_version,
                    "defender_data": asset.defender_data,
                    "tenable_data": asset.tenable_data,
                    "tags": asset.display_tags,
                }
                for asset in queryset
            ]
        else:
            assets = [
                {
                    "id": asset.pk,
                    "name": asset.name,
                    "aliases": asset.aliases,
                    "description": asset.description,
                    "contacts": asset.asset_contacts,
                    "systems": asset.associated_systems,
                    "os": asset.os,
                    "os_version": asset.os_version,
                    "tags": asset.display_tags,
                }
                for asset in queryset
            ]

        return JsonResponse(assets, safe=False)
