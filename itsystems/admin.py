from django.contrib import admin
from django.urls import path
from django.utils.translation import gettext_lazy as _

from reversion.admin import VersionAdmin

from .models import ITSystemRecord, Division, Seasonality, Status, Sensitivity, SystemType, Availability
from .views import ExportRegisterAsCSV, ImportRegisterChangesFromCSV


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
        "business_service_owner__email",
        "system_owner__email",
        "technology_custodian__email",
        "information_custodian__email",
        "seasonality__name",
        "availability__name",
        "disposal_authority",
        "retention_and_disposal",
        "ubcs",
        "sensitivity__name",
        "system_type__name",
    )

    autocomplete_fields = ("system_owner", "technology_custodian", "information_custodian", "business_service_owner")

    list_filter = (CustomStatusFilters, "division", "seasonality", "availability", "vital_records", "sensitivity", "system_type")

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
        ] + urls
        return urls
