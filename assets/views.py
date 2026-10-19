from django.views.generic import View
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control
from django.conf import settings
from django.http import JsonResponse

from assets.models import Asset, AssetTag, Vulnerability
from assets.enum_library import Severity, SeverityMT, State

class AssetAPIResource(View):
    """An API view that returns JSON of assets."""

    @method_decorator(cache_control(max_age=settings.API_RESPONSE_CACHE_SECONDS, private=True))
    def get(self, request, *args, **kwargs) -> JsonResponse:
        """
        Returns a json object recorded assets.
        Provides filtering functionality on ID, name, os, tag catgory, tag value.
        Has an additional flag of "show_tenable_data" that will modify the response to contain the raw tenable data used to generate the asset.
        """
        queryset = Asset.objects.all()

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
                queryset = Asset.objects.none()
        elif "tag_cat" in self.request.GET:  # By any tag inside a tag category
            queryset = queryset.filter(tags__category__name__iexact=self.request.GET["tag_cat"])
        elif "tag" in self.request.GET:  # By a tag across any tag category
            queryset = queryset.filter(tags__name__iexact=self.request.GET["tag"])

        # post-filter ordering for efficiency
        queryset = queryset.order_by("-total_active_vulns","-total_critical_vulns","name")

        if "tenable_data_only" in self.request.GET:
            assets = [asset.tenable_data for asset in queryset]
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
                    "active_vulns": asset.total_active_vulns,
                    "critical_vulns": asset.total_critical_vulns,
                }
                for asset in queryset
            ]

        return JsonResponse(assets, safe=False)

class VulnerabilityAPIResource(View):
    """An API view that returns JSON of assets."""

    # Classes used to lookup values for filtering
    SEVERITY_LOOKUP = {
        "INFO": Severity.INFO,
        "LOW": Severity.LOW,
        "MEDIUM": Severity.MEDIUM,
        "HIGH": Severity.HIGH,
        "CRITICAL": Severity.CRITICAL,
    }
    SEVERITY_MOD_TYPE_LOOKUP = {"NONE":SeverityMT.NONE, "RECASTED":SeverityMT.RECASTED, "ACCEPTED":SeverityMT.ACCEPTED}
    STATE_LOOKUP = {"OPEN":State.OPEN, "REOPENED":State.REOPENED, "FIXED":State.FIXED}

    @method_decorator(cache_control(max_age=settings.API_RESPONSE_CACHE_SECONDS, private=True))
    def get(self, request, *args, **kwargs) -> JsonResponse:
        """
        Returns a json object recorded vulns.
        Provides filtering functionality on finding_id, severity, severity_md_type, state, plugin_name, plugin_family, asset name, and it system code
        Has an additional flag of "show_raw_data" that will modify the response to contain the raw tenable data used to generate the asset.
        """
        queryset = Vulnerability.objects.all()
        # Queryset filtering.
        # By finding_id
        if "finding_id" in kwargs and kwargs["finding_id"]:
            queryset = queryset.filter(finding_id=kwargs["finding_id"])

        # By severity
        if "severity" in self.request.GET:
            sev_val = self.request.GET["severity"].upper()
            if sev_val in self.SEVERITY_LOOKUP: # Standard severity filter
                queryset = queryset.filter(severity=self.SEVERITY_LOOKUP[sev_val])
            elif sev_val.startswith("GT_") and sev_val[3:] in self.SEVERITY_LOOKUP: # Greater than filter
                queryset = queryset.filter(severity__gt=self.SEVERITY_LOOKUP[sev_val[3:]])
            elif sev_val.startswith("NOT_") and sev_val[4:] in self.SEVERITY_LOOKUP: # Exclusion filter
                queryset = queryset.exclude(severity=self.SEVERITY_LOOKUP[sev_val[4:]])

        # By Severity mod type
        if "severity_mod_type" in self.request.GET:
            sev_md_val = self.request.GET["severity_mod_type"].upper()
            if sev_md_val in self.SEVERITY_MOD_TYPE_LOOKUP: # Standard severity mod type filter
                queryset = queryset.filter(severity_modification_type=self.SEVERITY_MOD_TYPE_LOOKUP[sev_md_val])
            elif sev_md_val.startswith("NOT_") and sev_md_val[4:] in self.SEVERITY_MOD_TYPE_LOOKUP: # Exclusion filter
                queryset = queryset.exclude(severity_modification_type=self.SEVERITY_MOD_TYPE_LOOKUP[sev_md_val[4:]])

        # By state
        if "state" in self.request.GET:
            state_val = self.request.GET["state"].upper()
            if state_val in self.STATE_LOOKUP: # Standard state filter
                queryset = queryset.filter(state=self.STATE_LOOKUP[state_val])
            elif state_val.startswith("NOT_") and state_val[4:] in self.STATE_LOOKUP: # Exclusion filter
                queryset = queryset.exclude(state=self.STATE_LOOKUP[state_val[4:]])

        # By plugin_name
        if "plugin_name" in self.request.GET:
            queryset = queryset.filter(plugin__name__icontains=self.request.GET["plugin_name"])

        # by plugin_family
        if "plugin_family" in self.request.GET:
            queryset = queryset.filter(plugin__family__icontains=self.request.GET["plugin_family"])

        # by asset name
        if "asset" in self.request.GET:
            queryset = queryset.filter(asset__name__icontains=self.request.GET["asset"])

        # by it system code
        if "it_system" in self.request.GET:
            queryset = queryset.filter(asset__systems__system_id=self.request.GET["asset"])

        queryset = queryset.order_by(
        "-last_found",
        "-severity",
        "first_found",
        "asset__name",
    )

        if "tenable_data_only" in self.request.GET:
            vulns = [ vuln.raw_vuln_data for vuln in queryset]
        elif "expanded_fields" in self.request.GET:
            vulns = [
                    {
                        "finding_id": vuln.finding_id,
                        "asset": vuln.asset_name,
                        "state": vuln.get_state_display(),
                        "severity": vuln.get_severity_display(),
                        "severity_modification_type": vuln.get_severity_modification_type_display(),
                        "first_found": vuln.first_found,
                        "last_found": vuln.last_found,
                        "age_in_days": vuln.age_in_days,
                        "last_fixed": vuln.last_fixed,
                        "indexed": vuln.indexed,
                        "source": vuln.source,
                        "resurfaced_date": vuln.resurfaced_date,
                        "time_taken_to_fix": vuln.time_taken_to_fix,
                        "plugin_name": vuln.plugin_name,
                        "plugin_family": vuln.plugin_family,
                        "plugin_output": vuln.plugin_output,
                        "plugin_description": vuln.plugin_description,
                        "solution": vuln.solution,
                        "output": vuln.output,
                        "exploitability_ease": vuln.exploitability_ease,
                        "exploited_by_malware": vuln.exploited_by_malware,
                        "exploited_by_nessus": vuln.exploited_by_nessus,
                        "has_patch": vuln.has_patch,
                        "patch_publication_date": vuln.patch_publication_date,
                        "Cvss3 base score": vuln.cvss3_base_score,
                        "CVE": vuln.cve,
                        "workaround": vuln.workaround,
                    }
                    for vuln in queryset
            ]
        else:
            vulns = [
                    {
                        "finding_id": vuln.finding_id,
                        "asset": vuln.asset_name,
                        "state": vuln.get_state_display(),
                        "severity": vuln.get_severity_display(),
                        "severity_modification_type": vuln.get_severity_modification_type_display(),
                        "first_found": vuln.first_found,
                        "last_found": vuln.last_found,
                        "age_in_days": vuln.age_in_days,
                        "plugin_name": vuln.plugin_name,
                        "plugin_family": vuln.plugin_family,
                        "plugin_output": vuln.plugin_output,
                        "plugin_description": vuln.plugin_description,
                        "solution": vuln.solution,
                        "output": vuln.output,
                        "exploited_by_malware": vuln.exploited_by_malware,
                        "exploited_by_nessus": vuln.exploited_by_nessus,
                        "has_patch": vuln.has_patch,
                        "patch_publication_date": vuln.patch_publication_date,
                        "Cvss3 base score": vuln.cvss3_base_score,
                    }
                    for vuln in queryset
                ]

        return JsonResponse(vulns, safe=False)