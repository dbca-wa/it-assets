from django.contrib.admin import register, ModelAdmin, StackedInline, SimpleListFilter, TabularInline

from .models import Host, HostStatus, HostIP, ScanRange

class HostIPInline(TabularInline):
    model = HostIP
    extra = 1


@register(Host)
class HostAdmin(ModelAdmin):
    inlines = (HostIPInline,)


@register(HostStatus)
class HostStatusAdmin(ModelAdmin):
    list_display = ('host', 'date', 'ping_scan_range', 'ping_status_html', 'monitor_status_html', 'vulnerability_status_html', 'backup_status_html', 'patching_status_html')
    ordering = ('-date', '-ping_status', 'monitor_status', 'vulnerability_status', 'backup_status', 'patching_status')
    search_fields = ('host__name', 'host__host_ips__ip')
    list_filter = ('ping_scan_range',)
   
    """fieldsets = (
        ('Host details', {
            'fields': (
                'name', 'type'
            )
        }),
        ('Ping test', {
            'fields': (
                'ping_status', 'ping_scan_range'
            )
        }),
    )

    readonly_fields = ('name', 'type', 'ping_status', 'ping_scan_range', 'monitor_status', 'monitor_info', 'monitor_url',)"""


def enable_scan_ranges(modeladmin, request, queryset):
    queryset.update(enabled=True)
enable_scan_ranges.short_description = 'Enable scan ranges'


def disable_scan_ranges(modeladmin, request, queryset):
    queryset.update(enabled=False)
disable_scan_ranges.short_description = 'Disable scan ranges'


@register(ScanRange)
class ScanRangeAdmin(ModelAdmin):
    list_display = ('name', 'enabled', 'range')
    ordering = ('range',)
    actions = [enable_scan_ranges, disable_scan_ranges]
