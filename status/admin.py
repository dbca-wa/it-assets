from django.contrib.admin import register, ModelAdmin, StackedInline, SimpleListFilter, TabularInline

from django_q.tasks import async_task

from .models import Host, HostStatus, HostIP, ScanRange, ScanPlugin, ScanPluginParameter

class HostIPInline(TabularInline):
    model = HostIP
    extra = 1


@register(Host)
class HostAdmin(ModelAdmin):
    list_display = ('name',)
    ordering = ('name',)
    inlines = (HostIPInline,)



@register(HostStatus)
class HostStatusAdmin(ModelAdmin):
    list_display = ('host', 'date', 'ping_scan_range', 'ping_status_html', 'monitor_status_html', 'vulnerability_status_html', 'backup_status_html', 'patching_status_html')
    ordering = ('-date', '-ping_status', 'monitor_status', 'vulnerability_status', 'backup_status', 'patching_status')
    search_fields = ('host__name', 'host__host_ips__ip')
    list_filter = (
        'ping_scan_range',
    )
    date_hierarchy = 'date'

    actions = ('run_full_scan',)

    def run_full_scan(self, request, queryset):
        async_task('status.utils.run_all')
        self.message_user(request, 'A full scan has been scheduled.')
    run_full_scan.short_description = 'Run a full scan'


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



@register(ScanRange)
class ScanRangeAdmin(ModelAdmin):
    list_display = ('name', 'enabled', 'range')
    ordering = ('range',)
    actions = ('enable_scan_ranges', 'disable_scan_ranges', 'ping_sweep')

    def enable_scan_ranges(self, request, queryset):
        queryset.update(enabled=True)
        self.message_user(request, 'Scan ranges have been enabled.')
    enable_scan_ranges.short_description = 'Enable scan ranges'


    def disable_scan_ranges(self, request, queryset):
        queryset.update(enabled=False)
        self.message_user(request, 'Scan ranges have been disabled.')
    disable_scan_ranges.short_description = 'Disable scan ranges'

    def ping_sweep(self, request, queryset):
        for obj in queryset:
            async_task('status.utils.run_scan', obj.id)
        self.message_user('A ping sweep has been scheduled for these scan ranges.')
    ping_sweep.short_description = 'Run a ping sweep on this scan range'


class ScanPluginParameterInline(TabularInline):
    model = ScanPluginParameter
    extra = 1



@register(ScanPlugin)
class ScanPluginAdmin(ModelAdmin):
    list_display = ('name', 'enabled', 'plugin')
    ordering = ('name',)
    inlines = (ScanPluginParameterInline,)

    actions = ('run_scan_plugins',)

    def run_scan_plugins(self, request, queryset):
        for plugin in queryset:
            async_task('status.utils.run_plugin', plugin.id)
        self.message_user(request, 'The scan plugins have been scheduled to run.')
    run_scan_plugins.short_description = 'Run scan plugins'


