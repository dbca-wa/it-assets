from datetime import date, datetime
from django.http import HttpResponse
from django.views.generic import View

from .models import HostStatus
from .reports import host_status_export


class HostStatusReport(View):
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=host_status_{}_{}.xlsx'.format(date.today().isoformat(), datetime.now().strftime('%H%M'))

        statuses = HostStatus.objects.prefetch_related('host', 'ping_scan_range', 'monitor_plugin', 'vulnerability_plugin', 'backup_plugin', 'patching_plugin').filter(date=date.today()).order_by('host__name')

        response = host_status_export(response, statuses)
        return response
