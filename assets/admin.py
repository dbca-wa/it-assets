import json
from datetime import date, datetime, timedelta

from django.contrib import admin
from django.utils.html import mark_safe
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponse

from assets.models import Asset, AssetTagCategory, AssetTag, Vulnerability
from assets.enum_library import State, Severity, SeverityMT
from assets.exports import export_asset_vulns, export_vulns
from itsystems.models import ITSystemRecord
from itassets.admin_filters import DropdownFilterAllValues, DropdownFilterRelated, DropdownFilterRelatedOnly, DROPDOWN_TEMPLATE


class AssetTagInline(admin.TabularInline):
    """
    Used to dispay tag values inside the tag category admin page.
    Allows for tags and tag categories to be displayed heirarchically.
    """

    model = AssetTag
    extra = 0
    readonly_fields = ("total_assets",)
    fields = ("name", "total_assets")

    @admin.display(description="Total Tagged Assets")
    def total_assets(self, obj):
        """
        Provides a count of all assets with this tag, and includes a hyperlink to the pre-filtered admin asset page for this tag.
        """
        num_assets = obj.number_of_tagged_assets()
        # Links to the 'assets' admin page, filtered for assets containing that exact tag value
        url = reverse("service_desk_admin:assets_asset_changelist", query={f"{obj.category.name.lower()}_tag": obj.pk})
        return mark_safe(f"<a href='{url}'>{num_assets}</a>")


@admin.register(AssetTagCategory)
class AssetTagCategoryAdmin(admin.ModelAdmin):
    """
    Provides an admin interface for users to review tags and minor tag statistics.
    Uses an inline asset tag field to allow for a heirarchical structure.
    """

    search_fields = ("name",)
    readonly_fields = ("total_tags", "total_tagged_assets")
    list_display = ("category", "total_tags", "total_tagged_assets")
    inlines = [
        AssetTagInline,
    ]

    readonly_fields = ("total_tags",)
    fields = ("name", "total_tags")

    @admin.display(description="Category")
    def category(self, obj):
        return obj.name

    @admin.display(description="Total Tags")
    def total_tags(self, obj):
        """
        Provides a count of all tag values for this tag category.
        """
        return obj.number_of_values()

    @admin.display(description="Total Tagged Assets")
    def total_tagged_assets(self, obj):
        """
        Provides a count of all assets tagged with this category, and provides a link to a pre-filtered admin asset page for this tag category.
        """
        total_assets = sum(set([len(x.tagged_assets.all()) for x in obj.tag_values.all()]))
        # Links to the 'assets' admin page, filtered for any asset that contains tags of that category
        url = reverse("service_desk_admin:assets_asset_changelist", query={"tags__category__id__exact": obj.pk})
        return mark_safe(f"<a href='{url}'>{total_assets}</a>")


@admin.register(AssetTag)
class AssetTagAdmin(admin.ModelAdmin):
    """
    Registers the tag model with django admin so it can be used in autocomplete fields, but hides it from users.
    """

    def get_model_perms(self, request):
        return {}

    search_fields = ("name", "category__name")


@admin.register(Vulnerability)
class VulnerabilityAdmin(admin.ModelAdmin):
    # ==========================================
    #       Custom Filter classes & Config
    # ==========================================
    class StateFilter(admin.SimpleListFilter):
        """
        Standard State filter but adds in the option to exclude "Fixed".
        """

        template = DROPDOWN_TEMPLATE
        title = "State"
        parameter_name = "state"

        def lookups(self, request, model_admin):
            filter_list = [
                ("NF", "Not Fixed"),
            ]
            for key, val in Vulnerability.STATE_CHOICES.items():
                filter_list.append((key, _(val)))

            return filter_list

        def queryset(self, request, queryset):
            if self.value() == "NF":
                return queryset.exclude(state=State.FIXED)
            elif self.value() is not None:
                return queryset.filter(state=self.value())

    class SeverityFilter(admin.SimpleListFilter):
        """
        Standard Severity filter but adds some range options.
        """

        template = DROPDOWN_TEMPLATE
        title = "Severity"
        parameter_name = "severity"

        def lookups(self, request, model_admin):
            filter_list = [
                ("L", ">= Low"),
                ("M", ">= Medium"),
                ("H", ">= High"),
            ]
            for key, val in Vulnerability.SEVERITY_CHOICES.items():
                filter_list.append((key, _(val)))

            return filter_list

        def queryset(self, request, queryset):
            match self.value():
                case "L":
                    return queryset.filter(severity__gte=Severity.LOW)
                case "M":
                    return queryset.filter(severity__gte=Severity.MEDIUM)
                case "H":
                    return queryset.filter(severity__gt=Severity.HIGH)
                case _:
                    if self.value() is not None:
                        return queryset.filter(severity=self.value())

    class SeverityModTypeFilter(admin.SimpleListFilter):
        """
        Standard Severity Modification Type filter but adds in the option to exclude "Accepted".
        """

        template = DROPDOWN_TEMPLATE
        title = "Severity Modification Type"
        parameter_name = "severity_modification_type"

        def lookups(self, request, model_admin):
            filter_list = [("NA", "Not Accepted")]
            for key, val in Vulnerability.SEVERITY_MOD_TYPE_CHOICES.items():
                filter_list.append((key, _(val)))

            return filter_list

        def queryset(self, request, queryset):
            if self.value() == "NA":
                return queryset.exclude(severity_modification_type=SeverityMT.ACCEPTED)
            elif self.value() is not None:
                return queryset.filter(severity_modification_type=self.value())
    class LastFoundFilter(admin.SimpleListFilter):
        """
        A custom filter that allows users to filters by last_found within set week-by-week ranges
        """

        template = DROPDOWN_TEMPLATE
        title = "Last Found"
        parameter_name = "last_found"

        def lookups(self, request, model_admin):
            filter_list = [
                ("1", "0-1 Weeks Ago"),
                ("2", "1-2 Weeks Ago"),
                ("3", "2-3 Weeks Ago"),
                ("4", "3-4 Weeks Ago"),
                ("5", "4+ Weeks Ago"), 
                ]

            return filter_list

        def queryset(self, request, queryset):
            match self.value():
                case "1":
                    return queryset.filter(last_found__date__range=(datetime.now() - timedelta(weeks=1), datetime.now()))
                case "2":
                    return queryset.filter(last_found__date__range=(datetime.now() - timedelta(weeks=2), datetime.now()- timedelta(weeks=1)))
                case "3":
                    return queryset.filter(last_found__date__range=(datetime.now() - timedelta(weeks=3), datetime.now()- timedelta(weeks=2)))
                case "4":
                    return queryset.filter(last_found__date__range=(datetime.now() - timedelta(weeks=4), datetime.now()- timedelta(weeks=3)))
                case "5":
                    return queryset.filter(last_found__lte=datetime.now()-timedelta(weeks=4))
                case _:
                    return queryset

    # Set filters
    list_filter = (
        ("asset__systems", DropdownFilterRelatedOnly),
        ("asset", DropdownFilterRelated),
        StateFilter,
        SeverityFilter,
        SeverityModTypeFilter,
        LastFoundFilter,
    )

    # =================================
    #       Export actions & Config
    # =================================

    @admin.action(permissions=["view"], description="Export Vulns - Technical")
    def vulns_as_csv_technical(self, request, queryset):
        """
        Admin action that exports all selected vulnerabilities as a csv
        """
        return export_vulns_action(queryset=queryset)

    @admin.action(permissions=["view"], description="Export Vulns - Simple")
    def vulns_as_csv_simple(self, request, queryset):
        """
        Admin action that exports all selected vulnerabilities as a csv, but is simplified for tech custodians
        """
        return export_vulns_action(queryset=queryset, simple=True)

    # Set actions
    actions = [vulns_as_csv_simple, vulns_as_csv_technical]

    # ==================================
    #           Custom fields
    # ==================================

    @admin.display(description="Summary")
    def summarise(self, obj):
        return mark_safe(obj.html_summary)

    def plugin_pprint(self, obj=None):
        if obj and obj.plugin:
            return pprint_json(data=obj.plugin)

    def port_pprint(self, obj=None):
        if obj and obj.port:
            return pprint_json(data=obj.port)

    def scan_pprint(self, obj=None):
        if obj and obj.scan:
            return pprint_json(data=obj.scan)

    def software_vulns_pprint(self, obj=None):
        if obj and obj.software_vulns:
            return pprint_json(data=obj.software_vulns)

    def vpr_pprint(self, obj=None):
        if obj and obj.plugin and obj.plugin.get("vpr"):
            return pprint_json(data=obj.plugin["vpr"])

    plugin_pprint.short_description = "Plugin"
    port_pprint.short_description = "Port"
    scan_pprint.short_description = "Scan"
    software_vulns_pprint.short_description = "Software Vulnerabilities"
    vpr_pprint.short_description = "VPR"

    # ==========================================
    #       Admin list & change view config
    # ==========================================

    search_fields = (
        "asset__name",
        "finding_id",
        "plugin",
    )

    list_display = ("plugin_name", "asset__name", "severity", "state", "severity_modification_type", "last_found")

    ordering = (
        "-severity",
        "asset__name",
    )

    readonly_fields = (
        "summarise",
        "finding_id",
        "state",
        "severity",
        "severity_modification_type",
        "output",
        "first_found",
        "last_found",
        "last_fixed",
        "indexed",
        "source",
        "resurfaced_date",
        "time_taken_to_fix",
        "asset",
        "ipv4_addresses",
        "operating_systems",
        "plugin_id",
        "plugin_name",
        "vuln_age",
        "plugin_family",
        "plugin_description",
        "plugin_output",
        "exploitability_ease",
        "exploited_by_malware",
        "exploited_by_nessus",
        "cvss3_base_score",
        "cve",
        "has_patch",
        "patch_publication_date",
        "solution",
        "workaround",
        "plugin_pprint",
        "port_pprint",
        "scan_pprint",
        "software_vulns_pprint",
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "summarise",
                ),
            },
        ),
        (
            "General",
            {
                "fields": (
                    "finding_id",
                    "state",
                    "severity",
                    "severity_modification_type",
                    "output",
                    "first_found",
                    "last_found",
                    "last_fixed",
                    "indexed",
                    "source",
                    "resurfaced_date",
                    "time_taken_to_fix",
                ),
            },
        ),
        (
            "Asset",
            {
                "fields": (
                    "asset",
                    "ipv4_addresses",
                    "operating_systems",
                ),
            },
        ),
        (
            "Plugin",
            {
                "fields": (
                    "plugin_id",
                    "plugin_name",
                    "plugin_family",
                    "vuln_age",
                    "plugin_output",
                    "plugin_description",
                    "solution",
                    "has_patch",
                    "patch_publication_date",
                    "exploitability_ease",
                    "exploited_by_malware",
                    "exploited_by_nessus",
                    "cvss3_base_score",
                    "cve",
                    "workaround",
                ),
            },
        ),
        (
            "Raw Data",
            {
                "classes": ["collapse"],
                "fields": (
                    "plugin_pprint",
                    "port_pprint",
                    "scan_pprint",
                    "software_vulns_pprint",
                ),
            },
        ),
    )


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    # ==========================================
    #       Custom Filter classes & Config
    # ==========================================
    class ITSystemRegisterFilter(admin.SimpleListFilter):
        """
        Related only filter for IT systems, but includse a "Not Empty" option, which filters out empty options
        """

        template = DROPDOWN_TEMPLATE
        title = "IT System"
        parameter_name = "systems"

        def lookups(self, request, model_admin):
            filter_list = [("any", "Not Empty")]
            for sys in ITSystemRecord.objects.exclude(related_assets=None):
                filter_list.append((sys.pk, _(str(sys))))

            filter_list.append(("none", "-"))

            return filter_list

        def queryset(self, request, queryset):
            if self.value() == "any":
                return queryset.filter(systems__isnull=False)
            if self.value() == "none":
                return queryset.filter(systems__isnull=True)
            elif self.value() is not None:
                return queryset.filter(systems__pk__iexact=self.value())

    class TagFilterTemplate(admin.SimpleListFilter):
        """
        A custom tag filter template class to allow for filtering on categorized tags.
        Child classes must provide a class string variable for title, parameter_name, and category.
        """

        template = DROPDOWN_TEMPLATE

        def lookups(self, request, model_admin):
            filter_list = []

            tag_category, _c = AssetTagCategory.objects.get_or_create(name=self.category)
            location_tags = AssetTag.objects.filter(category=tag_category).order_by("name")
            for tag in location_tags:
                filter_list.append((tag.pk, _(tag.name)))

            return filter_list

        def queryset(self, request, queryset):
            if self.value() is not None:
                return queryset.filter(tags__id__exact=self.value())

    class LastSeenFilter(admin.SimpleListFilter):
        """
        A custom filter that allows users to filters by last_seen within set week-by-week ranges
        """

        template = DROPDOWN_TEMPLATE
        title = "Last Seen"
        parameter_name = "last_seen"

        def lookups(self, request, model_admin):
            filter_list = [
                ("1", "0-1 Weeks Ago"),
                ("2", "1-2 Weeks Ago"),
                ("3", "2-3 Weeks Ago"),
                ("4", "3-4 Weeks Ago"),
                ("5", "4+ Weeks Ago"), 
                ]

            return filter_list

        def queryset(self, request, queryset):
            match self.value():
                case "1":
                    return queryset.filter(last_seen__date__range=(datetime.now() - timedelta(weeks=1), datetime.now()))
                case "2":
                    return queryset.filter(last_seen__date__range=(datetime.now() - timedelta(weeks=2), datetime.now()- timedelta(weeks=1)))
                case "3":
                    return queryset.filter(last_seen__date__range=(datetime.now() - timedelta(weeks=3), datetime.now()- timedelta(weeks=2)))
                case "4":
                    return queryset.filter(last_seen__date__range=(datetime.now() - timedelta(weeks=4), datetime.now()- timedelta(weeks=3)))
                case "5":
                    return queryset.filter(last_seen__lte=datetime.now()-timedelta(weeks=4))
                case _:
                    return queryset

    def get_list_filter(self, request):
        """
        Dynamically creates filter classes from tags found in the db.
        Allows new tag categories to be created without the need to manually maintain the filters.
        """
        self.list_filter = self.list_filter_base + tuple(
            [
                type(
                    f"{cat.name}Filter",
                    (self.TagFilterTemplate,),
                    {"title": f"Tag: {cat.name}", "parameter_name": f"{cat.name.lower()}_tag", "category": cat.name},
                )
                for cat in AssetTagCategory.objects.all().order_by("name")
            ]
        )

        return super().get_list_filter(request)

    # Base filters - Dynamic tag filters are appended to this
    list_filter_base = (ITSystemRegisterFilter,LastSeenFilter, ("os", DropdownFilterAllValues), ("tags__category", DropdownFilterRelated))

    # =================================
    #       Export actions & Config
    # =================================

    @admin.action(permissions=["view"], description="Export Asset Vulns - Technical")
    def asset_export_as_csv_technical(self, request, queryset):
        """Exports all assets with their vulnerabilities as a csv"""
        return export_vulns_action(queryset=queryset, export_assets=True)

    @admin.action(permissions=["view"], description="Export critical Asset Vulns - Technical")
    def asset_export_critical_as_csv_technical(self, request, queryset):
        """Exports all assets with their critical vulnerabilities as a csv"""
        return export_vulns_action(queryset=queryset, critical_only=True, export_assets=True)

    @admin.action(permissions=["view"], description="Export Asset Vulns - Simple")
    def asset_export_as_csv_simple(self, request, queryset):
        """Exports all assets with their vulnerabilities as a csv, but simplified for tech custodians"""
        return export_vulns_action(queryset=queryset, simple=True, export_assets=True)

    @admin.action(permissions=["view"], description="Export critical Asset Vulns - Simple")
    def asset_export_critical_as_csv_simple(self, request, queryset):
        """Exports all assets with their critical vulnerabilities as a csv, but simplified for tech custodians"""
        return export_vulns_action(queryset=queryset, critical_only=True, simple=True, export_assets=True)

    actions = [
        asset_export_as_csv_simple,
        asset_export_critical_as_csv_simple,
        asset_export_as_csv_technical,
        asset_export_critical_as_csv_technical,
    ]

    # ==================================
    #           Custom fields
    # ==================================

    @admin.display(description="Active Vulns", ordering="total_active_vulns")
    def active_vulns(self, obj):
        """
        Provides a count of all active vulnerabilities of this asset, and includes a hyperlink to the pre-filtered admin vuln page for these assets.
        """
        num_vulns = obj.total_active_vulns
        # Links to the 'vulnerabilities' admin page, filtered for active vulns of this asset.
        url = reverse(
            "service_desk_admin:assets_vulnerability_changelist",
            query={"asset__id__exact": obj.pk, "severity_modification_type": "NA", "state": "NF"},
        )
        return mark_safe(f"<a href='{url}'>{num_vulns}</a>")

    @admin.display(description="Active Critical Vulns", ordering="total_critical_vulns")
    def active_critical_vulns(self, obj):
        """
        Provides a count of all active critical vulnerabilities of this asset, and includes a hyperlink to the pre-filtered admin vuln page for these assets.
        """
        num_vulns = obj.total_critical_vulns
        # Links to the 'vulnerabilities' admin page, filtered for active critical vulns of this asset.
        url = reverse(
            "service_desk_admin:assets_vulnerability_changelist",
            query={"asset__id__exact": obj.pk, "severity_modification_type": "NA", "state": "NF", "severity": Severity.CRITICAL},
        )
        return mark_safe(f"<a href='{url}'>{num_vulns}</a>")

    def defender_data_pprint(self, obj=None):
        if obj and obj.defender_data:
            return pprint_json(data=obj.defender_data)

    def tenable_data_pprint(self, obj=None):
        if obj and obj.tenable_data:
            return pprint_json(data=obj.tenable_data)

    defender_data_pprint.short_description = "Defender Data"
    tenable_data_pprint.short_description = "Tenable Data"

    # ==========================================
    #       Admin list & change view config
    # ==========================================

    ordering = ["name"]

    list_display = (
        "name",
        "custodian",
        "asset_type",
        "os",
        "os_version",
        "asset_contacts",
        "associated_systems",
        "display_tags",
        "active_vulns",
        "active_critical_vulns",
        "last_seen",
    )

    search_fields = ("name", "description", "contacts__email", "systems__name", "tags__name", "os", "os_version")

    autocomplete_fields = (
        "contacts",
        "systems",
        "tags",
    )

    readonly_fields = (
        "name",
        "asset_type",
        "custodian",
        "os",
        "os_version",
        "first_seen",
        "last_seen",
        "last_modified",
        "defender_data_pprint",
        "tenable_data_pprint",
        "active_vulns",
        "active_critical_vulns",
        "ipv4s",
        "operating_systems",
    )

    fieldsets = (
        (
            "Overview",
            {
                "fields": ("name", "asset_type", "active_vulns", "active_critical_vulns", "description"),
            },
        ),
        (
            "Associations",
            {
                "fields": (
                    "custodian",
                    "contacts",
                    "systems",
                    "tags",
                ),
            },
        ),
        (
            "Technical Info",
            {
                "fields": (
                    "os",
                    "os_version",
                    "ipv4s",
                    "operating_systems",
                ),
            },
        ),
        (
            "Meta-Data",
            {
                "fields": ("first_seen", "last_seen", "last_modified"),
            },
        ),
        (
            "Raw Data",
            {
                "classes":["collapse"],
                "fields": (
                    "tenable_data_pprint",
                ),
            },
        ),
    )


# ==========================================
#           Helper functions
# ==========================================


def pprint_json(data=None):
    """
    JSON pretty print, makes json fields more readable
    """
    result = ""
    if data:
        result = json.dumps(data, indent=4, sort_keys=True)
        result = f"<pre>{result}</pre>"
        result = mark_safe(result)
    return result


def export_vulns_action(queryset, critical_only: bool = False, simple: bool = False, export_assets: bool = False):
    """
    Helper function for export actions to export vulnerabilities.
    """
    # Set severity exclusions
    if critical_only:
        exclude_list = [Severity.INFO, Severity.LOW, Severity.MEDIUM, Severity.HIGH]
    else:
        exclude_list = [Severity.INFO]

    # Prepends "asset_" to filename if it's an asset export
    exp_string = "asset_" if export_assets else ""

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f"attachment; filename={exp_string}vulns_{date.today().isoformat()}_{datetime.now().strftime('%H%M')}.csv"
    )
    if export_assets:
        return export_asset_vulns(response=response, assets=queryset, severity_exclude_list=exclude_list, simple=simple)
    else:
        return export_vulns(response=response, vulns=queryset, simple=simple)
