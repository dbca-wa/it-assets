from django.contrib.admin import ModelAdmin

from itassets.utils import ModelDescMixin

from .models import ITSystem


# @register(ITSystem)
class ITSystemAdmin(ModelDescMixin, ModelAdmin):
    model_description = ITSystem.__doc__
    list_display = (
        "system_id",
        "name",
        "status",
        "cost_centre",
        "owner",
        "technology_custodian",
        "information_custodian",
    )
    list_filter = ("status",)
    search_fields = (
        "system_id",
        "owner__email",
        "name",
        "acronym",
        "description",
        "technology_custodian__email",
        "link",
        "description",
        "cost_centre__code",
    )
    readonly_fields = (
        "system_id",
        "name",
        "link",
        "status",
        "owner",
        "technology_custodian",
        "information_custodian",
        "description",
    )
    fieldsets = [
        (
            "Overview",
            {
                "description": '<span class="errornote">Data in these fields is maintained in SharePoint.</span>',
                "fields": (
                    "system_id",
                    "name",
                    "link",
                    "status",
                    "owner",
                    "technology_custodian",
                    "information_custodian",
                    "description",
                ),
            },
        ),
    ]
    # Override the default change_list.html template:
    change_list_template = "admin/registers/itsystem/change_list.html"
    save_on_top = True

    def has_change_permission(self, request, obj=None):
        # The point of truth for IT Systems is now Sharepoint, therefore adding new objects here is disallowed.
        return False

    def has_add_permission(self, request):
        # The point of truth for IT Systems is now Sharepoint, therefore adding new objects here is disallowed.
        return False

    def has_delete_permission(self, request, obj=None):
        # The point of truth for IT Systems is now Sharepoint, therefore deleting objects here is disallowed.
        return False
