from django.contrib.admin import register, ModelAdmin, StackedInline, SimpleListFilter

from .models import Host, ScanRange

@register(Host)
class HostAdmin(ModelAdmin):
    list_display = ('name', 'ping_status', 'monitor_status', 'vulnerability_status', 'backup_status', 'patching_status')
    ordering = ('-ping_status', 'monitor_status', 'vulnerability_status', 'backup_status', 'patching_status')


@register(ScanRange)
class ScanRangeAdmin(ModelAdmin):
    list_display = ('range', 'name')
    ordering = ('range',)
