from django.urls import reverse
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.html import format_html

from json2html import json2html
import datetime


class ScanRange(models.Model):
    name = models.CharField(max_length=256)
    range = models.CharField(max_length=2048)
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ScanPlugin(models.Model):
    PLUGIN_CHOICES = (
        ("monitor_prtg", "Monitor - PRTG"),
        ("vulnerability_nessus", "Vulnerability - Nessus"),
        ("backup_acronis", "Backup - Acronis"),
        ("backup_aws", "Backup - AWS snapshots"),
        ("backup_azure", "Backup - Azure snapshots"),
        ("backup_storagesync", "Backup - Azure Storage Sync Services"),
        # ('backup_veeam', 'Backup - Veeam'),
        # ('backup_restic', 'Backup - Restic'),
        ("backup_phoenix", "Backup - Druva Phoenix"),
        ("patching_oms", "Patching - Azure OMS"),
    )
    PLUGIN_PARAMS = {
        "monitor_prtg": ("PRTG_BASE", "PRTG_USERNAME", "PRTG_PASSHASH", "PRTG_URL"),
        "vulnerability_nessus": (
            "NESSUS_BASE",
            "NESSUS_ACCESS_KEY",
            "NESSUS_SECRET_KEY",
            "NESSUS_SCAN_FOLDER",
            "NESSUS_URL",
        ),
        "backup_acronis": (
            "ACRONIS_BASE",
            "ACRONIS_USERNAME",
            "ACRONIS_PASSWORD",
            "ACRONIS_URL",
        ),
        "backup_aws": ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"),
        "backup_azure": (
            "AZURE_TENANT",
            "AZURE_APP_ID",
            "AZURE_APP_KEY",
            "AZURE_SUBSCRIPTION_ID",
            "AZURE_VAULT_NAME",
        ),
        "backup_storagesync": (
            "AZURE_TENANT",
            "AZURE_APP_ID",
            "AZURE_APP_KEY",
            "AZURE_SUBSCRIPTION_ID",
            "AZURE_RESOURCE_GROUP",
            "AZURE_STORAGE_SYNC_NAME",
        ),
        "backup_phoenix": ("PHOENIX_USERNAME", "PHOENIX_PASSWORD", "PHOENIX_SITE_ID"),
        "patching_oms": (
            "AZURE_TENANT",
            "AZURE_APP_ID",
            "AZURE_APP_KEY",
            "AZURE_LOG_WORKSPACE",
        ),
    }

    name = models.CharField(max_length=256)
    plugin = models.CharField(max_length=32, choices=PLUGIN_CHOICES)
    enabled = models.BooleanField(default=True)

    def run(self, date=None):
        import status.plugins as plugins

        if date is None:
            date = datetime.date.today()
        if hasattr(plugins, self.plugin):
            getattr(plugins, self.plugin)(self, date)
        else:
            print("STUB: {}".format(self.plugin))

    def __str__(self):
        return self.name

    class Meta:
        ordering = ("name",)


class ScanPluginParameter(models.Model):
    scan_plugin = models.ForeignKey(
        ScanPlugin, on_delete=models.CASCADE, related_name="params"
    )
    name = models.CharField(max_length=256)
    value = models.CharField(max_length=2048, blank=True)

    class Meta:
        unique_together = ("scan_plugin", "name")
        ordering = ("scan_plugin", "name")


@receiver(post_save, sender=ScanPlugin)
def scan_plugin_post_save(sender, signal, instance, **kwargs):
    if instance.plugin in ScanPlugin.PLUGIN_PARAMS:
        for param in ScanPlugin.PLUGIN_PARAMS[instance.plugin]:
            obj, _ = ScanPluginParameter.objects.get_or_create(
                scan_plugin=instance, name=param
            )
            obj.save()


class Host(models.Model):
    TYPE_CHOICES = (
        (0, "Server"),
        (1, "Embedded device"),
    )
    name = models.CharField(max_length=256, unique=True)
    type = models.SmallIntegerField(choices=TYPE_CHOICES, default=0)

    active = models.BooleanField(default=True)

    def ip_list(self):
        return ",".join(self.host_ips.values_list("ip", flat=True))

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class HostStatus(models.Model):
    STATUS_CHOICES = (
        (0, "N/A"),
        (1, "No record"),
        (2, "Unhealthy"),
        (3, "OK"),
    )

    STATUS_COLOURS = {
        0: ("inherit", "inherit"),
        1: ("#fcd8d8", "#6f0000"),
        2: ("#fedfb3", "#8d3f00"),
        3: ("#ddf7c5", "#376d04"),
    }

    host = models.ForeignKey(Host, on_delete=models.CASCADE, related_name="statuses")
    date = models.DateField()

    ping_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    ping_scan_range = models.ForeignKey(
        ScanRange, null=True, on_delete=models.SET_NULL, related_name="hosts"
    )
    ping_output = None
    ping_url = None

    monitor_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    monitor_plugin = models.ForeignKey(
        ScanPlugin,
        null=True,
        on_delete=models.SET_NULL,
        related_name="monitor_statuses",
    )
    monitor_output = models.CharField(max_length=2048, blank=True)
    monitor_info = JSONField(default=dict)
    monitor_url = models.URLField(max_length=256, null=True)

    vulnerability_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    vulnerability_plugin = models.ForeignKey(
        ScanPlugin,
        null=True,
        on_delete=models.SET_NULL,
        related_name="vulnerability_statuses",
    )
    vulnerability_output = models.CharField(max_length=2048, blank=True)
    vulnerability_info = JSONField(default=dict)
    vulnerability_url = models.URLField(max_length=256, null=True)

    backup_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    backup_plugin = models.ForeignKey(
        ScanPlugin, null=True, on_delete=models.SET_NULL, related_name="backup_statuses"
    )
    backup_output = models.CharField(max_length=2048, blank=True)
    backup_info = JSONField(default=dict)
    backup_url = models.URLField(max_length=256, null=True)

    patching_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    patching_plugin = models.ForeignKey(
        ScanPlugin,
        null=True,
        on_delete=models.SET_NULL,
        related_name="patching_statuses",
    )
    patching_output = models.CharField(max_length=2048, blank=True)
    patching_info = JSONField(default=dict)
    patching_url = models.URLField(max_length=256, null=True)

    # HTML rendered statuses for the admin list view
    def host_html(self):
        url = reverse("admin:status_host_change", args=(self.host.id,))
        return format_html('<a href="{}">{}</a>', url, self.host.name)

    host_html.short_description = "Host"

    def _status_html(self, prefix):
        status = getattr(self, "{}_status".format(prefix))
        status_url = getattr(self, "{}_url".format(prefix))
        status_output = getattr(self, "{}_output".format(prefix))
        status_name = getattr(self, "get_{}_status_display".format(prefix))()

        body = '<div style="text-align: center; font-weight: bold; background-color: {}; color: {}; border-radius: 2px;"'
        args = [*self.STATUS_COLOURS[status]]
        if status_output:
            body += 'title="{}">'
            args.append(status_output)
        else:
            body += ">"

        if status_url:
            body += '<a target="_blank" href="{}">'
            args.append(status_url)
        body += "{}"
        args.append(status_name)
        if status_url:
            body += "</a>"
        body += "</div>"
        return format_html(body, *args)

    def _info_html(self, prefix):
        info = getattr(self, "{}_info".format(prefix))
        return format_html(json2html.convert(json=info))

    def _url_html(self, prefix):
        url = getattr(self, "{}_url".format(prefix))
        if url is None:
            return "None"
        return format_html('<a href="{}">{}</a>', url, url)

    def ping_status_html(self):
        return self._status_html("ping")

    ping_status_html.admin_order_field = "ping_status"
    ping_status_html.short_description = "Ping"

    def monitor_status_html(self):
        return self._status_html("monitor")

    monitor_status_html.admin_order_field = "monitor_status"
    monitor_status_html.short_description = "Monitor"

    def vulnerability_status_html(self):
        return self._status_html("vulnerability")

    vulnerability_status_html.admin_order_field = "vulnerability_status"
    vulnerability_status_html.short_description = "Vulnerability"

    def backup_status_html(self):
        return self._status_html("backup")

    backup_status_html.admin_order_field = "backup_status"
    backup_status_html.short_description = "Backup"

    def patching_status_html(self):
        return self._status_html("patching")

    patching_status_html.admin_order_field = "patching_status"
    patching_status_html.short_description = "Patching"

    def monitor_info_html(self):
        return self._info_html("monitor")

    monitor_info_html.short_description = "Monitor info"

    def vulnerability_info_html(self):
        return self._info_html("vulnerability")

    vulnerability_info_html.short_description = "Vulnerability info"

    def backup_info_html(self):
        return self._info_html("backup")

    backup_info_html.short_description = "Backup info"

    def patching_info_html(self):
        return self._info_html("patching")

    patching_info_html.short_description = "Patching info"

    def monitor_url_html(self):
        return self._url_html("monitor")

    monitor_url_html.short_description = "Monitor URL"

    def vulnerability_url_html(self):
        return self._url_html("vulnerability")

    vulnerability_url_html.short_description = "Vulnerability URL"

    def backup_url_html(self):
        return self._url_html("backup")

    backup_url_html.short_description = "Backup URL"

    def patching_url_html(self):
        return self._url_html("patching")

    patching_url_html.short_description = "Patching URL"

    def __str__(self):
        return "{} - {}".format(self.host.name, self.date.isoformat())

    class Meta:
        verbose_name_plural = "host statuses"
        get_latest_by = "date"
        unique_together = ("host", "date")


class HostIP(models.Model):
    ip = models.GenericIPAddressField(unique=True)
    last_seen = models.DateTimeField(auto_now=True)
    host = models.ForeignKey(Host, on_delete=models.CASCADE, related_name="host_ips")

    def __str__(self):
        return self.ip
