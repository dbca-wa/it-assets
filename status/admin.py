from django.contrib.admin import register, ModelAdmin, StackedInline, SimpleListFilter, TabularInline
from django.urls import path
from django_q.tasks import async_task

from .models import Host, HostStatus, HostIP, ScanRange, ScanPlugin, ScanPluginParameter
from .views import HostStatusReport

class HostIPInline(TabularInline):
    model = HostIP
    extra = 1


@register(Host)
class HostAdmin(ModelAdmin):
    list_display = ('name', 'active', 'ip_list')
    ordering = ('name',)
    inlines = (HostIPInline,)
    list_filter = ('active', 'type')
    actions = ('enable_hosts', 'disable_hosts')
    search_fields = ('name', 'host_ips__ip')

    def enable_hosts(self, request, queryset):
        queryset.update(active=True)
        self.message_user(request, 'Hosts have been enabled.')
    enable_hosts.short_description = 'Enable hosts'

    def disable_hosts(self, request, queryset):
        queryset.update(active=False)
        self.message_user(request, 'Hosts have been disabled.')
    disable_hosts.short_description = 'Disable hosts'


@register(HostStatus)
class HostStatusAdmin(ModelAdmin):
    list_display = ('host', 'date', 'ping_scan_range', 'ping_status_html', 'monitor_status_html', 'vulnerability_status_html', 'backup_status_html', 'patching_status_html')
    ordering = ('-date', '-ping_status', 'monitor_status', 'vulnerability_status', 'backup_status', 'patching_status')
    search_fields = ('host__name', 'host__host_ips__ip', 'ping_scan_range__name')
    list_filter = (
        'ping_scan_range',
    )
    date_hierarchy = 'date'

    actions = ('run_full_scan',)

    def run_full_scan(self, request, queryset):
        async_task('status.utils.run_all')
        self.message_user(request, 'A full scan has been scheduled.')
    run_full_scan.short_description = 'Run a full scan'

    def has_delete_permission(self, request, obj=None):
        return False

    fieldsets = (
        ('Host details', {
            'fields': (
                'host_html', 'date', 'ping_status_html', 'ping_scan_range'
            )
        }),
        ('Monitoring', {
            'fields': (
                'monitor_status_html', 'monitor_plugin', 'monitor_output', 'monitor_info_html', 'monitor_url_html',
            )
        }),
        ('Vulnerability testing', {
            'fields': (
                'vulnerability_status_html', 'vulnerability_plugin', 'vulnerability_output', 'vulnerability_info_html', 'vulnerability_url_html',
            )
        }),
        ('Backup', {
            'fields': (
                'backup_status_html', 'backup_plugin', 'backup_output', 'backup_info_html', 'backup_url_html',
            )
        }),
        ('Patching automation', {
            'fields': (
                'patching_status_html', 'patching_plugin', 'patching_output', 'patching_info_html', 'patching_url_html',
            )
        }),
    )

    readonly_fields = (
        'host_html', 'date', 'ping_status_html', 'ping_scan_range',
        'monitor_status_html', 'monitor_plugin', 'monitor_output', 'monitor_info_html', 'monitor_url_html',
        'vulnerability_status_html', 'vulnerability_plugin', 'vulnerability_output', 'vulnerability_info_html', 'vulnerability_url_html',
        'backup_status_html', 'backup_plugin', 'backup_output', 'backup_info_html', 'backup_url_html',
        'patching_status_html', 'patching_plugin', 'patching_output', 'patching_info_html', 'patching_url_html',
    )

    def get_urls(self):
        urls = super(HostStatusAdmin, self).get_urls()
        urls = [
            path('report/', HostStatusReport.as_view(), name='host_status_report'),
        ] + urls
        return urls



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
        self.message_user(request, 'A ping sweep has been scheduled for these scan ranges.')
    ping_sweep.short_description = 'Run a ping sweep on this scan range'


class ScanPluginParameterInline(TabularInline):
    model = ScanPluginParameter
    extra = 1



@register(ScanPlugin)
class ScanPluginAdmin(ModelAdmin):
    list_display = ('name', 'enabled', 'plugin')
    ordering = ('name',)
    inlines = (ScanPluginParameterInline,)

    actions = ('enable_scan_plugins', 'disable_scan_plugins', 'run_scan_plugins',)

    def enable_scan_plugins(self, request, queryset):
        queryset.update(enabled=True)
        self.message_user(request, 'Scan plugins have been enabled.')
    enable_scan_plugins.short_description = 'Enable scan plugins'

    def disable_scan_plugins(self, request, queryset):
        queryset.update(enabled=False)
        self.message_user(request, 'Scan plugins have been disabled.')
    disable_scan_plugins.short_description = 'Disable scan plugins'

    def run_scan_plugins(self, request, queryset):
        for plugin in queryset:
            async_task('status.utils.run_plugin', plugin.id)
        self.message_user(request, 'The scan plugins have been scheduled to run.')
    run_scan_plugins.short_description = 'Run scan plugins'


