# Generated by Django 2.0.9 on 2018-10-09 04:31

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('organisation', '0007_auto_20180829_1733'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('registers', '0002_auto_20181009_0902'),
    ]

    operations = [
        migrations.CreateModel(
            name='Incident',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('description', models.TextField(help_text='Short description of the incident')),
                ('priority', models.CharField(choices=[('P0', 'Low - P0'), ('P1', 'Moderate - P1'), ('P2', 'High - P2'), ('P3', 'Critical - P3')], db_index=True, max_length=16)),
                ('start', models.DateTimeField(help_text='Initial detection time')),
                ('resolution', models.DateTimeField(blank=True, help_text='Resolution time', null=True)),
                ('url', models.URLField(blank=True, help_text='Incident report URL (e.g. Freshdesk ticket)', max_length=2048, null=True, verbose_name='URL')),
                ('detection', models.PositiveIntegerField(blank=True, choices=[(0, 'Monitoring process'), (1, 'OIM staff report'), (2, 'User/custodian report')], help_text='The method by which the incident was initially detected', null=True)),
                ('category', models.PositiveIntegerField(blank=True, choices=[(0, 'Outage'), (1, 'Service degredation'), (2, 'Security')], null=True)),
                ('workaround', models.TextField(blank=True, help_text='Workaround/business continuity actions performed', null=True)),
                ('root_cause', models.TextField(blank=True, help_text='Root cause analysis/summary', null=True)),
                ('remediation', models.TextField(blank=True, help_text='Remediation/improvement actions performed/planned', null=True)),
                ('it_systems', models.ManyToManyField(blank=True, help_text='IT System(s) affected', to='registers.ITSystem', verbose_name='IT Systems')),
                ('locations', models.ManyToManyField(blank=True, help_text='Location(s) affected', to='organisation.Location')),
                ('manager', models.ForeignKey(blank=True, help_text='Incident manager', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='manager', to=settings.AUTH_USER_MODEL)),
                ('owner', models.ForeignKey(blank=True, help_text='Incident owner', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='owner', to=settings.AUTH_USER_MODEL)),
                ('platforms', models.ManyToManyField(blank=True, help_text='Platforms/services affected', to='registers.Platform')),
            ],
            options={
                'ordering': ('-created',),
            },
        ),
        migrations.CreateModel(
            name='IncidentLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('log', models.TextField()),
                ('incident', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='registers.Incident')),
            ],
            options={
                'ordering': ('created',),
            },
        ),
    ]
