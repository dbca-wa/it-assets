from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils.safestring import mark_safe
from json2html import json2html
import os

from organisation.models import DepartmentUser, Location
from tracking.models import CommonFields, Computer


class Vendor(models.Model):
    """Represents the vendor of a product (software, hardware or service).
    """
    name = models.CharField(
        max_length=256, unique=True, help_text='E.g. Dell, Cisco, etc.')
    details = models.TextField(null=True, blank=True)
    account_rep = models.CharField(max_length=200, null=True, blank=True)
    contact_email = models.EmailField(null=True, blank=True)
    contact_phone = models.CharField(max_length=50, null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    extra_data = JSONField(default=dict, null=True, blank=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class Asset(CommonFields):
    """Abstract model class to represent fields common to all asset types.
    """
    vendor = models.ForeignKey(
        Vendor, on_delete=models.PROTECT, help_text='Vendor/reseller from whom this asset was purchased.')
    date_purchased = models.DateField(null=True, blank=True)
    purchased_value = models.DecimalField(
        max_digits=20, decimal_places=2, blank=True, null=True,
        help_text='The amount paid for this asset, inclusive of any upgrades (excluding GST).')
    notes = models.TextField(null=True, blank=True)
    service_request_url = models.URLField(
        max_length=2000, verbose_name='Service request URL', null=True, blank=True,
        help_text='URL (e.g. Freshdesk, Jira, etc.) of the service request for purchase of this asset.')

    class Meta:
        abstract = True


class HardwareModel(models.Model):
    """Represents the vendor model type for a physical hardware asset.
    """
    TYPE_CHOICES = (
        ('Air conditioner', 'Air conditioner'),
        ('Camera - Compact', 'Camera - Compact'),
        ('Camera - Conference', 'Camera - Conference'),
        ('Camera - Security (IP)', 'Camera - Security (IP)'),
        ('Camera - Other', 'Camera - Other'),
        ('Cellular repeater', 'Cellular repeater'),
        ('Computer - Desktop', 'Computer - Desktop'),
        ('Computer - Laptop', 'Computer - Laptop'),
        ('Computer - Monitor', 'Computer - Monitor'),
        ('Computer - Peripheral', 'Computer - Peripheral'),
        ('Computer - Tablet PC', 'Computer - Tablet PC'),
        ('Computer - Other', 'Computer - Other'),
        ('Environmental monitor', 'Environmental monitor'),
        ('Network - Media converter', 'Network - Media converter'),
        ('Network - Modem', 'Network - Modem'),
        ('Network - Module or card', 'Network - Module or card'),
        ('Network - Music On Hold', 'Network - Music On Hold'),
        ('Network - Power injector', 'Network - Power injector'),
        ('Network - Router', 'Network - Router'),
        ('Network - Switch (Ethernet)', 'Network - Switch (Ethernet)'),
        ('Network - Switch (FC)', 'Network - Switch (FC)'),
        ('Network - Wireless AP', 'Network - Wireless AP'),
        ('Network - Wireless bridge', 'Network - Wireless bridge'),
        ('Network - Wireless controller', 'Network - Wireless controller'),
        ('Network - Other', 'Network - Other'),
        ('Office Equipment - Other', 'Office Equipment - Other'),
        ('Phone - Conference', 'Phone - Conference'),
        ('Phone - Desk', 'Phone - Desk'),
        ('Phone - Gateway', 'Phone - Gateway'),
        ('Phone - Mobile', 'Phone - Mobile'),
        ('Phone - Wireless or portable', 'Phone - Wireless or portable'),
        ('Phone - Other', 'Phone - Other'),
        ('Power Distribution Unit', 'Power Distribution Unit'),
        ('Printer - Multifunction copier', 'Printer - Multifunction copier'),
        ('Printer - Plotter', 'Printer - Plotter'),
        ('Printer - Server', 'Printer - Server'),
        ('Printer - Workgroup', 'Printer - Workgroup'),
        ('Projector', 'Projector'),
        ('Rack', 'Rack'),
        ('Server - Blade', 'Server - Blade'),
        ('Server - Rackmount', 'Server - Rackmount'),
        ('Server - Tower', 'Server - Tower'),
        ('Storage - Disk array', 'Storage - Disk array'),
        ('Storage - Hard Drive', 'Storage - Hard Drive'),
        ('Storage - NAS', 'Storage - NAS'),
        ('Storage - SAN', 'Storage - SAN'),
        ('Storage - Other', 'Storage - Other'),
        ('Speaker', 'Speaker'),
        ('Tape autoloader', 'Tape autoloader'),
        ('Tape drive', 'Tape drive'),
        ('Telecom - Testing Device', 'Telecom - Testing Device'),
        ('UPS', 'UPS'),
        ('Other', 'Other'),
    )

    model_type = models.CharField(
        max_length=50, choices=TYPE_CHOICES, help_text='The broad category of this hardware model.')
    vendor = models.ForeignKey(
        Vendor, on_delete=models.PROTECT, verbose_name='manufacturer',
        help_text='The manufacturer of this hardware model (e.g. Dell, Cisco, Apple).')
    model_no = models.CharField(
        max_length=50, verbose_name='model number',
        help_text='''The short model number (eg. '7945G' for a Cisco 7956G phone).
            Do not enter the class (eg. '7900 series') or the product code (eg. 'WS-7945G=')''')
    notes = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ('model_no',)
        unique_together = (('vendor', 'model_no'))

    def __str__(self):
        return self.model_no


class HardwareAsset(Asset):
    """Represents a physical hardware asset.
    """
    STATUS_CHOICES = (
        ('In storage', 'In storage'),
        ('Deployed', 'Deployed'),
        ('Disposed', 'Disposed'),
        ('Transferred', 'Transferred'),
    )
    asset_tag = models.CharField(max_length=10, unique=True, help_text='OIM asset tag number.')
    finance_asset_tag = models.CharField(
        max_length=10, null=True, blank=True,
        help_text='The Finance Services Branch asset number for (leave blank if unknown).')
    hardware_model = models.ForeignKey(
        HardwareModel, on_delete=models.PROTECT, help_text="The manufacturer's hardware model.")
    status = models.CharField(
        max_length=50, choices=STATUS_CHOICES, default='In storage')
    serial = models.CharField(
        max_length=50, help_text='The serial number or service tag.')
    location = models.ForeignKey(Location, on_delete=models.PROTECT, null=True, blank=True)
    assigned_user = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, null=True, blank=True)
    tracked_computer = models.OneToOneField(Computer, on_delete=models.PROTECT, null=True, blank=True)
    local_property = models.BooleanField(
        default=False, help_text='''Indicates an item that is not registered with Finance (i.e. is
            valued <$5,000 and is not defined as portable and attractive).''')
    is_asset = models.BooleanField(
        default=False, help_text='Indicates an item that is valued >$5,000')
    warranty_end = models.DateField(
        null=True, blank=True, help_text='Expiry date of hardware warranty period (if applicable).')

    class Meta:
        ordering = ('-asset_tag',)

    def __str__(self):
        return self.asset_tag

    def get_extra_data_html(self):
        if not self.extra_data:
            return mark_safe('')
        return mark_safe(json2html.convert(json=self.extra_data))


class HardwareInvoice(models.Model):
    """A limited model to store uploaded hardware asset invoice copies.
    """
    asset = models.ForeignKey(HardwareAsset, on_delete=models.CASCADE)
    upload = models.FileField(
        max_length=512, upload_to='uploads/%Y/%m/%d',
        help_text='A digital copy of the asset invoice (e.g. PDF, JPG or PNG)'
    )

    def __str__(self):
        return os.path.basename(self.upload.name)


class SoftwareAsset(Asset):
    """Represents a purchased, proprietary software asset (licence or subscription).
    Does not include FOSS or other free/non-purchased software.
    """
    LICENSE_CHOICES = (
        (0, 'License/perpetual'),
        (1, 'Subscription/SaaS'),
    )
    name = models.CharField(max_length=512, unique=True)
    publisher = models.ForeignKey(
        Vendor, null=True, blank=True, on_delete=models.PROTECT, related_name='publisher',
        help_text='The publisher of this software (may differ from the vendor/reseller).')
    url = models.URLField(max_length=2000, verbose_name='URL', null=True, blank=True)
    support = models.TextField(
        null=True, blank=True, help_text='Description of the scope of vendor support.')
    support_expiry = models.DateField(
        null=True, blank=True, help_text='Expiry date of vendor support (if applicable).')
    license = models.PositiveSmallIntegerField(
        choices=LICENSE_CHOICES, null=True, blank=True,
        help_text='The license type/arrangement for this software asset')
    license_details = models.TextField(
        null=True, blank=True,
        help_text='Description of license arrangement (custodian of license key/s, etc.)')
    license_count = models.PositiveSmallIntegerField(
        default=1, null=True, blank=True,
        help_text='The number of licenses, seats or subscriptions provided with this software asset.')
    installations = models.ManyToManyField(
        Computer, blank=True, help_text='Department computers on which this software is physically installed.')

    def __str__(self):
        return self.name
