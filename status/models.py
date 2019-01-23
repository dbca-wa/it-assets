
from django.contrib.postgres.fields import JSONField
from django.db import models


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

    name = models.CharField(max_length=256)
    type = models.SmallIntegerField(choices=TYPE_CHOICES, default=0)

    ping_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    ping_scan_range = models.ForeignKey(ScanRange, null=True, on_delete=models.SET_NULL, related_name='hosts')

    monitor_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    monitor_info = JSONField(default=dict)
    
    vulnerability_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    vulnerability_info = JSONField(default=dict)

    backup_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    backup_info = JSONField(default=dict)

    patching_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    patching_info = JSONField(default=dict)

    def __str__(self):
        return self.name


class HostIP(models.Model):
    ip = models.GenericIPAddressField(unique=True)
    last_seen = models.DateTimeField(auto_now=True)
    host = models.ForeignKey(Host, on_delete=models.CASCADE, related_name='host_ips')

    def __str__(self):
        return self.ip
