import json

from django.contrib import admin
from django.utils.html import mark_safe
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from assets.models import Asset, AssetTagCategory, AssetTag, Vulnerability
from itassets.admin_filters import DropdownFilterAllValues, DropdownFilterChoices, DropdownFilterRelated, DROPDOWN_TEMPLATE


class AssetTagInline(admin.TabularInline):
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
    class StateFilter(admin.SimpleListFilter):
        """
        Standard State filter but adds in the option to exclude "Fixed".
        """
        template = DROPDOWN_TEMPLATE
        title = "State"
        parameter_name = "state"

        def lookups(self, request, model_admin):
            filter_list = [
                ("NF","Not Fixed"),
            ]
            for key, val in Vulnerability.STATE_CHOICES.items():
                filter_list.append((key, _(val)))

            return filter_list

        def queryset(self, request, queryset):
                if self.value() == "NF":
                    return queryset.exclude(state="F")                
                elif self.value() is not None:
                    return queryset.filter(severity=self.value())
                
    class SeverityFilter(admin.SimpleListFilter):
        """
        Standard Severity filter but adds some range options.
        """
        template = DROPDOWN_TEMPLATE
        title = "Severity"
        parameter_name = "severity"

        def lookups(self, request, model_admin):
            filter_list = [
                (-1,">= Low"),
                (-2,">= Medium"),
                (-3,">= High"),
            ]
            for key, val in Vulnerability.SEVERITY_CHOICES.items():
                filter_list.append((key, _(val)))

            return filter_list

        def queryset(self, request, queryset):
            match self.value():
                case "-1":
                    return queryset.filter(severity__gt=0)
                case "-2":
                    return queryset.filter(severity__gt=1)
                case "-3":
                    return queryset.filter(severity__gt=2)
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
            filter_list = [("NA","Not Accepted")]
            for key, val in Vulnerability.SEVERITY_MOD_TYPE_CHOICES.items():
                filter_list.append((key, _(val)))

            return filter_list

        def queryset(self, request, queryset):
            if self.value() == "NA":
                return queryset.exclude(severity_modification_type="A")
            elif self.value() is not None:
                return queryset.filter(severity_modification_type=self.value())


    search_fields = (
        "asset__name",
        "finding_id",
    )

    list_display = (
        "plugin_name",
        "plugin_family",
        "asset__name",
        "state",
        "severity",
        "severity_modification_type"
        )

    list_filter = (
        ("asset", DropdownFilterRelated),
        StateFilter,
        SeverityFilter,
        SeverityModTypeFilter,
    )

    ordering = ("asset__name", "state", "severity")

    readonly_fields = (
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
        "vpr_pprint",
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
            "General",
            {
                "fields":(
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
            }
        ),
        (
            "Asset",
            { 
                "fields":(
                    "asset",
                    "ipv4_addresses",
                    "operating_systems",
                    ),
            }
        ),
        (
            "Plugin",
            {
                "fields":(
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
                    "vpr_pprint",
                    "workaround",
                    ),
            }
        ),
        (
            "Raw Data",
            {
                "fields":(
                    "plugin_pprint",
                    "port_pprint",
                    "scan_pprint",
                    "software_vulns_pprint",
                    ),
            }
        ),
    )

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


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
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
    list_filter_base = (("os", DropdownFilterAllValues), ("tags__category", DropdownFilterRelated))

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
    )

    search_fields = (
        "name", 
        "description", 
        "contacts__email", 
        "systems__name", 
        "tags__name", 
        "os", 
        "os_version"
    )

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
    )

    fieldsets = (
        (
            "Overview",
            {
                "fields": (
                    "name", 
                    "asset_type", 
                    "active_vulns",
                    "active_critical_vulns",
                    "description"
                    ),
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
                    "defender_data_pprint",
                    "tenable_data_pprint",
                ),
            },
        ),
        (
            "Meta-Data",
            {
                "fields": ("first_seen", "last_seen", "last_modified"),
            },
        ),
    )

    @admin.display(description="Active Vulns", ordering="total_vulns")
    def active_vulns(self, obj):
        """
        Provides a count of all active vulnerabilities of this asset, and includes a hyperlink to the pre-filtered admin vuln page for these assets.
        """
        num_vulns = len(obj.get_active_vulns())
        # Links to the 'vulnerabilities' admin page, filtered for active vulns of this asset.
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"asset__id__exact": obj.pk,"severity_modification_type":"NA","state":"NF" })
        return mark_safe(f"<a href='{url}'>{num_vulns}</a>")

    @admin.display(description="Active Critical Vulns", ordering="total_critical_vulns")
    def active_critical_vulns(self, obj):
        """
        Provides a count of all active critical vulnerabilities of this asset, and includes a hyperlink to the pre-filtered admin vuln page for these assets.
        """
        num_vulns = len(obj.get_active_vulns(severity=4))
        # Links to the 'vulnerabilities' admin page, filtered for active critical vulns of this asset.
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"asset__id__exact": obj.pk,"severity_modification_type":"NA","state":"NF", "severity":4})
        return mark_safe(f"<a href='{url}'>{num_vulns}</a>")


    def defender_data_pprint(self, obj=None):
        if obj and obj.defender_data:
            return pprint_json(data=obj.defender_data)

    def tenable_data_pprint(self, obj=None):
        if obj and obj.tenable_data:
            return pprint_json(data=obj.tenable_data)

    defender_data_pprint.short_description = "Defender Data"
    tenable_data_pprint.short_description = "Tenable Data"

def pprint_json(data=None):
    result = ""
    if data:
        result = json.dumps(data, indent=4, sort_keys=True)
        result = f"<pre>{result}</pre>"
        result = mark_safe(result)
    return result