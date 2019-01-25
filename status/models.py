
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils.html import format_html


class ScanRange(models.Model):
    name = models.CharField(max_length=256)
    range = models.CharField(max_length=256)

    def __str__(self):
        return '{} ({})'.format(self.name, self.range)


class Host(models.Model):
    TYPE_CHOICES = (
        (0, 'Server'),
        (1, 'Embedded device'),
    )

    STATUS_CHOICES = (
        (0, 'N/A'),
        (1, 'Failure'),
        (2, 'Unhealthy'),
        (3, 'OK'),
    )

    STATUS_COLOURS = {
        0: ('inherit', 'inherit'),
        1: ('#fcd8d8', '#6f0000'),
        2: ('#fedfb3', '#8d3f00'),
        3: ('#ddf7c5', '#376d04'),
    }

    name = models.CharField(max_length=256)
    type = models.SmallIntegerField(choices=TYPE_CHOICES, default=0)

    ping_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    ping_scan_range = models.ForeignKey(ScanRange, null=True, on_delete=models.SET_NULL, related_name='hosts')
    ping_url = None

    monitor_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    monitor_info = JSONField(default=dict)
    monitor_url = models.URLField(max_length=256, null=True)

    vulnerability_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    vulnerability_info = JSONField(default=dict)
    vulnerability_url = models.URLField(max_length=256, null=True)

    backup_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    backup_info = JSONField(default=dict)
    backup_url = models.URLField(max_length=256, null=True)

    patching_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    patching_info = JSONField(default=dict)
    patching_url = models.URLField(max_length=256, null=True)

    # HTML rendered statuses for the admin list view
    def _status_html(self, prefix):
        status = getattr(self, '{}_status'.format(prefix))
        status_url = getattr(self, '{}_url'.format(prefix))
        status_name = getattr(self, 'get_{}_status_display'.format(prefix))()
        if status_url:
            return format_html('<div style="text-align: center; font-weight: bold; background-color: {}; color: {}; border-radius: 2px;"><a href="{}">{}</a></div>',
                *self.STATUS_COLOURS[status],
                status_url,
                status_name,
            )
        return format_html('<div style="text-align: center; font-weight: bold; background-color: {}; color: {}; border-radius: 2px;">{}</div>',
            *self.STATUS_COLOURS[status],
            status_name
        )

    def ping_status_html(self):
        return self._status_html('ping')
    ping_status_html.admin_order_field = 'ping_status'
    ping_status_html.short_description = 'Ping'

    def monitor_status_html(self):
        return self._status_html('monitor')
    monitor_status_html.admin_order_field = 'monitor_status'
    monitor_status_html.short_description = 'Monitor'

    def vulnerability_status_html(self):
        return self._status_html('vulnerability')
    vulnerability_status_html.admin_order_field = 'vulnerability_status'
    vulnerability_status_html.short_description = 'Vulnerability'

    def backup_status_html(self):
        return self._status_html('backup')
    backup_status_html.admin_order_field = 'backup_status'
    backup_status_html.short_description = 'Backup'

    def patching_status_html(self):
        return self._status_html('patching')
    patching_status_html.admin_order_field = 'patching_status'
    patching_status_html.short_description = 'Patching'

    def __str__(self):
        return self.name


class HostIP(models.Model):
    ip = models.GenericIPAddressField(unique=True)
    last_seen = models.DateTimeField(auto_now=True)
    host = models.ForeignKey(Host, on_delete=models.CASCADE, related_name='host_ips')

    def __str__(self):
        return self.ip
