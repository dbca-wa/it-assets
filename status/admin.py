from django.contrib.admin import register, ModelAdmin, StackedInline, SimpleListFilter, TabularInline

from .models import Host, HostIP, ScanRange

class HostIPInline(TabularInline):
    model = HostIP
    extra = 1


@register(Host)
class HostAdmin(ModelAdmin):
    list_display = ('name', 'ping_scan_range', 'ping_status_html', 'monitor_status_html', 'vulnerability_status_html', 'backup_status_html', 'patching_status_html')
    ordering = ('-ping_status', 'monitor_status', 'vulnerability_status', 'backup_status', 'patching_status')
    search_fields = ('name', 'host_ips__ip')
    list_filter = ('ping_scan_range',)

    inlines = (HostIPInline,)


@register(ScanRange)
class ScanRangeAdmin(ModelAdmin):
    list_display = ('range', 'name')
    ordering = ('range',)
