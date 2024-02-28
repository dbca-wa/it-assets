from django.contrib.admin import register, ModelAdmin, SimpleListFilter

from itassets.utils import ModelDescMixin
from .models import ITSystem


@register(ITSystem)
class ITSystemAdmin(ModelDescMixin, ModelAdmin):

    class PlatformFilter(SimpleListFilter):
        """SimpleListFilter to filter on True/False if an object has a value for platform.
        """
        title = 'platform'
        parameter_name = 'platform_boolean'

        def lookups(self, request, model_admin):
            return (
                ('true', 'Present'),
                ('false', 'Absent'),
            )

        def queryset(self, request, queryset):
            if self.value() == 'true':
                return queryset.filter(platform__isnull=False)
            if self.value() == 'false':
                return queryset.filter(platform__isnull=True)

    model_description = ITSystem.__doc__
    list_display = (
        'system_id',
        'name',
        'status',
        'cost_centre',
        'owner',
        'technology_custodian',
        'information_custodian',
        'seasonality',
        'availability',
    )
    list_filter = (
        'status', 'system_type', 'availability', 'seasonality', 'recovery_category', PlatformFilter,
        'infrastructure_location',
    )
    search_fields = (
        'system_id', 'owner__email', 'name', 'acronym', 'description',
        'technology_custodian__email', 'link', 'documentation',
        'cost_centre__code',
    )
    readonly_fields = (
        'system_id', 'name', 'link', 'status', 'owner', 'technology_custodian', 'information_custodian',
        'availability', 'seasonality', 'description',
    )
    raw_id_fields = (
        'owner', 'technology_custodian', 'information_custodian', 'cost_centre', 'bh_support', 'ah_support')
    fieldsets = [
        ('Overview', {
            'description': '<span class="errornote">Data in these fields is maintained in SharePoint.</span>''',
            'fields': (
                'system_id',
                'name',
                'link',
                'status',
                'owner',
                'technology_custodian',
                'information_custodian',
                'availability',
                'seasonality',
                'description',
            )
        }),
        ('Technical information', {
            'description': '<span class="errornote">Data in these fields is used for OIM reporting purposes.</span>',
            'fields': (
                'bh_support',
                'ah_support',
                'cost_centre',
                'system_type',
                'infrastructure_location',
                'backups',
                'recovery_category',
                'emergency_operations',
                'online_bookings',
                'visitor_safety',
            ),
        }),
        ('Retention and disposal', {
            'description': '<span class="errornote">Data in these fields is used to record how long that data generated by the system should be retained for.</span>',
            'fields': (
                'defunct_date',
                'retention_reference_no',
                'disposal_action',
                'custody',
                'retention_comments',
            ),
        }),
    ]
    # Override the default change_list.html template:
    change_list_template = 'admin/registers/itsystem/change_list.html'
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
