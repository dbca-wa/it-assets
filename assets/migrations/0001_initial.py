# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from assets.models import UTCCreatedField, UTCLastModifiedField
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Asset',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', UTCCreatedField(editable=False)),
                ('modified', UTCLastModifiedField(editable=False)),
                ('asset_tag', models.CharField(unique=True, max_length=10)),
                ('finance_asset_tag', models.CharField(help_text='The asset number for this sevices, as issued by Finance (leave blank if unsure)', max_length=10, blank=True)),
                ('status', models.CharField(default='In storage.', max_length=50, choices=[('In storage', 'In storage'), ('Deployed', 'Deployed'), ('Disposed', 'Disposed')])),
                ('serial', models.CharField(help_text='For Dell machines, enter the Service Tag.', max_length=50)),
                ('date_purchased', models.DateField(default=datetime.datetime.now)),
                ('purchased_value', models.DecimalField(help_text='Enter the amount paid for this asset, inclusive of any permanent modules or upgrades, and excluding GST.', null=True, max_digits=20, decimal_places=2, blank=True)),
                ('assigned_user', models.CharField(help_text='Enter the username of the assigned user.', max_length=50, null=True, blank=True)),
                ('notes', models.TextField(blank=True)),
                ('creator', models.ForeignKey(related_name='assets_asset_created', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-asset_tag'],
            },
        ),
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', UTCCreatedField(editable=False)),
                ('modified', UTCLastModifiedField(editable=False)),
                ('supplier_ref', models.CharField(help_text="Enter the supplier's reference or invoice number for this order.", max_length=50, blank=True)),
                ('job_number', models.CharField(help_text='Enter the DEC job number relating to this order.', max_length=50, blank=True)),
                ('date', models.DateField(help_text='The date as shown on the invoice', null=True, blank=True)),
                ('cost_centre_name', models.CharField(help_text='The name of the cost centre that owns this asset for financial purposes.', max_length=50, blank=True)),
                ('cost_centre_number', models.IntegerField(help_text='The cost centre that owns this asset for financial purposes.', null=True, blank=True)),
                ('etj_number', models.CharField(max_length=20, verbose_name='ETJ number', blank=True)),
                ('total_value', models.DecimalField(help_text='Enter the total value of the invoice, excluding GST.', null=True, max_digits=20, decimal_places=2, blank=True)),
                ('notes', models.TextField(blank=True)),
                ('creator', models.ForeignKey(related_name='assets_invoice_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('modifier', models.ForeignKey(related_name='assets_invoice_modified', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-job_number'],
            },
        ),
        migrations.CreateModel(
            name='Location',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', UTCCreatedField(editable=False)),
                ('modified', UTCLastModifiedField(editable=False)),
                ('name', models.CharField(help_text='Enter a specific location - a cupboard or room number.', max_length=50)),
                ('block', models.CharField(help_text="eg. 'Block 10' (if applicable)", max_length=50, blank=True)),
                ('site', models.CharField(help_text="Enter the standard DEC site, eg. 'Kensington' or 'Northcliffe'. If the device is portable, enter 'Portable'.", max_length=50)),
                ('creator', models.ForeignKey(related_name='assets_location_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('modifier', models.ForeignKey(related_name='assets_location_modified', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['site', 'block', 'name'],
            },
        ),
        migrations.CreateModel(
            name='Model',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', UTCCreatedField(editable=False)),
                ('modified', UTCLastModifiedField(editable=False)),
                ('model_type', models.CharField(max_length=50, verbose_name='type', choices=[('Air conditioner', 'Air conditioner'), ('Camera - Compact', 'Camera - Compact'), ('Camera - SLR', 'Camera - SLR'), ('Camera - Security (IP)', 'Camera - Security (IP)'), ('Camera - Security (non-IP)', 'Camera - Security (non-IP)'), ('Camera - Other', 'Camera - Other'), ('Chassis', 'Chassis'), ('Computer - Desktop', 'Computer - Desktop'), ('Computer - Docking station', 'Computer - Docking station'), ('Computer - Input device', 'Computer - Input device'), ('Computer - Laptop', 'Computer - Laptop'), ('Computer - Misc Accessory', 'Computer - Misc Accessory'), ('Computer - Monitor', 'Computer - Monitor'), ('Computer - Tablet PC', 'Computer - Tablet PC'), ('Computer - Other', 'Computer - Other'), ('Environmental monitor', 'Environmental monitor'), ('Network - Hub', 'Network - Hub'), ('Network - Media converter', 'Network - Media converter'), ('Network - Modem', 'Network - Modem'), ('Network - Module or card', 'Network - Module or card'), ('Network - Power injector', 'Network - Power injector'), ('Network - Router', 'Network - Router'), ('Network - Switch (Ethernet)', 'Network - Switch (Ethernet)'), ('Network - Switch (FC)', 'Network - Switch (FC)'), ('Network - Wireless AP', 'Network - Wireless AP'), ('Network - Wireless bridge', 'Network - Wireless bridge'), ('Network - Wireless controller', 'Network - Wireless controller'), ('Network - Other', 'Network - Other'), ('Phone - Conference', 'Phone - Conference'), ('Phone - Desk', 'Phone - Desk'), ('Phone - Gateway', 'Phone - Gateway'), ('Phone - Mobile', 'Phone - Mobile'), ('Phone - Wireless or portable', 'Phone - Wireless or portable'), ('Phone - Other', 'Phone - Other'), ('Power Distribution Unit', 'Power Distribution Unit'), ('Printer - Fax machine', 'Printer - Fax machine'), ('Printer - Local', 'Printer - Local'), ('Printer - Local Multifunction', 'Printer - Local Multifunction'), ('Printer - Multifunction copier', 'Printer - Multifunction copier'), ('Printer - Plotter', 'Printer - Plotter'), ('Printer - Workgroup', 'Printer - Workgroup'), ('Printer - Other', 'Printer - Other'), ('Projector', 'Projector'), ('Rack', 'Rack'), ('Server - Blade', 'Server - Blade'), ('Server - Rackmount', 'Server - Rackmount'), ('Server - Tower', 'Server - Tower'), ('Storage - Disk array', 'Storage - Disk array'), ('Storage - NAS', 'Storage - NAS'), ('Storage - SAN', 'Storage - SAN'), ('Storage - Other', 'Storage - Other'), ('Speaker', 'Speaker'), ('Tablet', 'Tablet'), ('Tape autoloader', 'Tape autoloader'), ('Tape drive', 'Tape drive'), ('UPS', 'UPS'), ('Other', 'Other')])),
                ('model', models.CharField(help_text="Enter the short model number here (eg. '7945G' for a Cisco 7956G phone). Do not enter the class (eg. '7900 series') or the product code (eg. 'WS-7945G=')", max_length=50)),
                ('lifecycle', models.IntegerField(help_text='Enter in years how long we should keep items of this model before they get decomissioned. Desktops should generally be three years, servers and networking equipment five years.', max_length=10)),
                ('notes', models.TextField(blank=True)),
                ('creator', models.ForeignKey(related_name='assets_model_created', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['manufacturer', 'model'],
            },
        ),
        migrations.CreateModel(
            name='Supplier',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', UTCCreatedField(editable=False)),
                ('modified', UTCLastModifiedField(editable=False)),
                ('name', models.CharField(help_text='eg. Dell, Cisco', max_length=200)),
                ('account_rep', models.CharField(max_length=200, blank=True)),
                ('contact_email', models.EmailField(max_length=254, blank=True)),
                ('contact_phone', models.CharField(max_length=50, blank=True)),
                ('website', models.URLField(blank=True)),
                ('notes', models.TextField(blank=True)),
                ('creator', models.ForeignKey(related_name='assets_supplier_created', editable=False, to=settings.AUTH_USER_MODEL)),
                ('modifier', models.ForeignKey(related_name='assets_supplier_modified', editable=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='model',
            name='manufacturer',
            field=models.ForeignKey(to='assets.Supplier'),
        ),
        migrations.AddField(
            model_name='model',
            name='modifier',
            field=models.ForeignKey(related_name='assets_model_modified', editable=False, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='invoice',
            name='supplier',
            field=models.ForeignKey(to='assets.Supplier'),
        ),
        migrations.AddField(
            model_name='asset',
            name='invoice',
            field=models.ForeignKey(blank=True, to='assets.Invoice', null=True),
        ),
        migrations.AddField(
            model_name='asset',
            name='location',
            field=models.ForeignKey(to='assets.Location'),
        ),
        migrations.AddField(
            model_name='asset',
            name='model',
            field=models.ForeignKey(to='assets.Model'),
        ),
        migrations.AddField(
            model_name='asset',
            name='modifier',
            field=models.ForeignKey(related_name='assets_asset_modified', editable=False, to=settings.AUTH_USER_MODEL),
        ),
    ]
