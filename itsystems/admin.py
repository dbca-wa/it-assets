from django.contrib import admin
from django.urls import path
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponse
from django.utils.timezone import localtime as now

from reversion.admin import VersionAdmin
from itassets.admin_filters import DropdownFilterRelated, DropdownFilterRelatedOnly, DropdownFilterBoolean, DropdownFilterChoices, DROPDOWN_TEMPLATE
from assets.exports import export_itsystem_vulns, export_project_vulns
from assets.enum_library import Severity
from .models import ITSystemRecord, Division, Seasonality, Status, Sensitivity, SystemType, Availability, Project
from .views import ExportRegisterAsCSV, ImportRegisterChangesFromCSV, ExportProjectsAsCSV, ExportQuarterlyAsCSV


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Status)
class StatusAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Seasonality)
class SeasonalityAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Sensitivity)
class SensitivityAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(SystemType)
class SystemTypeAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(ITSystemRecord)
class ITSystemRecordAdmin(VersionAdmin):
    class CustomStatusFilters(admin.SimpleListFilter):
        """
        Extends the standard functionality of a "Status" filter by adding 2 additional filters.
        Any Production: Returns results that have "Production" in the status name.
        Not Decommissioned: Returns any result that doesn't have "Decommissioned" in the status name.
        """

        title = _("Status")
        parameter_name = "status"
        template = DROPDOWN_TEMPLATE

        def lookups(self, request, model_admin):
            status_list = Status.objects.all()
            filter_list = []
            for status in status_list:
                filter_list.append((status.pk, _(status.name)))
            filter_list.extend(
                [
                    ("all_prod", _("Any Production")),
                    ("not_decom", _("Not Decommissioned")),
                ]
            )

            return filter_list

        def queryset(self, request, queryset):
            if self.value() == "all_prod":
                return queryset.filter(status__name__icontains="Production")
            if self.value() == "not_decom":
                return queryset.exclude(status__name__icontains="Decommissioned")

            status_list = Status.objects.all().filter(pk=self.value())
            if len(status_list) == 1:
                return queryset.filter(status=status_list[0])

    def has_vuln_permission(self, request):
        """Only allows users to use the action if they can view vulns"""
        return request.user.has_perm("assets.view_vulnerability")

    @admin.action(permissions=["vuln"], description="Export actionable Vulns - Technical")
    def itsystem_export_as_csv_technical(self, request, queryset):
        """Exports all related assets with their vulnerabilities as a csv"""
        return export_vulns_action(queryset=queryset)

    @admin.action(permissions=["vuln"], description="Export actionable critical Vulns - Technical")
    def itsystem_export_critical_as_csv_technical(self, request, queryset):
        """Exports all related assets with their critical vulnerabilities as a csv"""
        return export_vulns_action(queryset=queryset, critical_only=True)

    @admin.action(permissions=["vuln"], description="Export actionable Vulns - Simple")
    def itsystem_export_as_csv_simple(self, request, queryset):
        """Exports all related assets with their vulnerabilities as a csv, but simplified for tech custodians"""
        return export_vulns_action(queryset=queryset, simple=True)

    @admin.action(permissions=["vuln"], description="Export actionable critical Vulns - Simple")
    def itsystem_export_critical_as_csv_simple(self, request, queryset):
        """Exports all related assets with their critical vulnerabilities as a csv, but simplified for tech custodians"""
        return export_vulns_action(queryset=queryset, critical_only=True, simple=True)

    actions = [
        itsystem_export_as_csv_simple,
        itsystem_export_as_csv_technical,
        itsystem_export_critical_as_csv_simple,
        itsystem_export_critical_as_csv_technical,
    ]

    change_list_template = "admin/itsystems/itsystemrecord/change_list.html"

    ordering = ["system_id"]

    list_display = (
        "system_id",
        "name",
        "status",
        "division",
        "short_description",
        "link",
        "business_service_owner",
        "system_owner",
        "technology_custodian",
        "information_custodian",
        "seasonality",
        "availability",
        "file_store_link",
        "vital_records",
        "disposal_authority",
        "retention_and_disposal",
        "ubcs",
        "sensitivity",
        "system_type",
    )

    readonly_fields = (
        "created_date",
        "created_by",
        "modified_date",
        "modified_by",
    )

    fieldsets = (
        (
            "Overview",
            {
                "fields": (
                    "system_id",
                    "name",
                    "division",
                    "status",
                    "description",
                ),
            },
        ),
        (
            "Details",
            {
                "fields": (
                    "link",
                    "file_store_link",
                    "seasonality",
                    "availability",
                ),
            },
        ),
        (
            "Contacts",
            {
                "fields": (
                    "business_service_owner",
                    "system_owner",
                    "technology_custodian",
                    "information_custodian",
                ),
            },
        ),
        (
            "Record Keeping",
            {
                "fields": (
                    "vital_records",
                    "disposal_authority",
                    "retention_and_disposal",
                    "sensitivity",
                    "system_type",
                    "ubcs",
                ),
            },
        ),
        (
            "Meta-Data",
            {
                "description": "Automatically captured during creation & modification",
                "fields": (
                    "created_by",
                    "created_date",
                    "modified_by",
                    "modified_date",
                ),
            },
        ),
    )

    search_fields = (
        "system_id",
        "name",
        "status__name",
        "division__name",
        "description",
        "link",
        "business_service_owner__email",
        "system_owner__email",
        "technology_custodian__email",
        "information_custodian__email",
        "seasonality__name",
        "availability__name",
        "file_store_link",
        "disposal_authority",
        "retention_and_disposal",
        "ubcs",
        "sensitivity__name",
        "system_type__name",
    )

    autocomplete_fields = ("system_owner", "technology_custodian", "information_custodian", "business_service_owner")

    list_filter = (
        CustomStatusFilters,
        ("division", DropdownFilterRelated),
        ("seasonality", DropdownFilterRelated),
        ("availability", DropdownFilterRelated),
        ("vital_records", DropdownFilterBoolean),
        ("sensitivity", DropdownFilterRelated),
        ("system_type", DropdownFilterRelated),
    )

    # Updates meta-data upon save.
    # Populates Created_* fields only during creation
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user.email
        obj.modified_by = request.user.email
        return super().save_model(request, obj, form, change)

    # Retrieves read-only fields, but only allows editing of system_id during creation.
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj=obj)
        if obj:
            readonly_fields = tuple(readonly_fields) + ("system_id",)
        return readonly_fields

    # Provides admin URLs for the import & export buttons
    def get_urls(self):
        urls = super().get_urls()
        info = self.opts.app_label, self.opts.model_name
        urls = [
            path(
                "import/",
                ImportRegisterChangesFromCSV.as_view(),
                name=f"{info[0]}_{info[1]}_import",
            ),
            path(
                "export/",
                ExportRegisterAsCSV.as_view(),
                name=f"{info[0]}_{info[1]}_export",
            ),
            path(
                "quarterly_export/",
                ExportQuarterlyAsCSV.as_view(),
                name=f"{info[0]}_{info[1]}_quarterlyexport",
            ),
        ] + urls
        return urls

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):

    # =================================
    #       Export actions & Config
    # =================================

    def has_vuln_permission(self, request):
        """Only allows users to use the action if they can view vulns"""
        return request.user.has_perm("assets.view_vulnerability")

    @admin.action(permissions=["vuln"], description="Export actionable Vulns - Technical")
    def project_export_as_csv_technical(self, request, queryset):
        """Exports all projects with their vulnerabilities as a csv"""
        return export_vulns_action(queryset=queryset, export_projects=True)

    @admin.action(permissions=["vuln"], description="Export actionable critical Vulns - Technical")
    def project_export_critical_as_csv_technical(self, request, queryset):
        """Exports all projects with their critical vulnerabilities as a csv"""
        return export_vulns_action(queryset=queryset, critical_only=True, export_projects=True)

    @admin.action(permissions=["vuln"], description="Export actionable Vulns - Simple")
    def project_export_as_csv_simple(self, request, queryset):
        """Exports all projects with their vulnerabilities as a csv, but simplified for tech custodians"""
        return export_vulns_action(queryset=queryset, simple=True, export_projects=True)

    @admin.action(permissions=["vuln"], description="Export actionable critical Vulns - Simple")
    def project_export_critical_as_csv_simple(self, request, queryset):
        """Exports all projects with their critical vulnerabilities as a csv, but simplified for tech custodians"""
        return export_vulns_action(queryset=queryset, critical_only=True, simple=True, export_projects=True)
    
    actions = [
        project_export_as_csv_technical,
        project_export_critical_as_csv_technical,
        project_export_as_csv_simple,
        project_export_critical_as_csv_simple,
    ]

    readonly_fields = ("associated_systems",)
    list_display = ("id","name","initiative_id","stage", "associated_systems")

    autocomplete_fields = ("systems",)

    search_fields = (
        "id",
        "name",
        "initiative_id",
    )

    search_help_text = "Search by ID, Name, or Initiative ID"

    list_filter = (("stage",DropdownFilterChoices),("systems", DropdownFilterRelatedOnly))

    fieldsets = (
        (
            "Project Info",
            {
                "fields": (
                    "id",
                    "name",
                    "initiative_id",
                ),
            },
        ),
        (
            "Associations",
            {
                "fields": (
                    "systems",
                ),
            },
        ),
    )


    def get_urls(self):
        urls = super().get_urls()
        info = self.opts.app_label, self.opts.model_name
        urls = [
            path(
                "export/",
                ExportProjectsAsCSV.as_view(),
                name=f"{info[0]}_{info[1]}_export",
            ),
        ] + urls
        return urls


def export_vulns_action(queryset, critical_only: bool = False, simple: bool = False, export_projects=False) -> HttpResponse:
    """
    Helper function for export actions to export vulnerabilities.
    """

    if export_projects:
        name_prefix = "project"
    else:
        name_prefix = "itsystem"

    # Set severity exclusions
    if critical_only:
        exclude_list = [Severity.INFO, Severity.LOW, Severity.MEDIUM, Severity.HIGH]
    else:
        exclude_list = [Severity.INFO]

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f"attachment; filename={name_prefix}_vulns_{now().strftime('%Y-%m-%d_%H%M')}.csv"

    if export_projects:
        return export_project_vulns(response=response, projects=queryset, severity_exclude_list=exclude_list, simple=simple)
    else:
        return export_itsystem_vulns(response=response, systems=queryset, severity_exclude_list=exclude_list, simple=simple)