# Generated by Django 2.2.21 on 2021-05-25 06:37

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('rancher', '0026_auto_20210525_1028'),
    ]

    operations = [
        migrations.CreateModel(
            name='OperatingSystem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(editable=False, max_length=64)),
                ('version', models.CharField(editable=False, max_length=64, null=True)),
            ],
            options={
                'ordering': ['name', 'version'],
                'unique_together': {('name', 'version')},
            },
        ),
        migrations.AlterField(
            model_name='containerimage',
            name='scan_status',
            field=models.SmallIntegerField(choices=[(0, 'Not Scan'), (-1, 'Scan Failed'), (-2, 'Parse Failed'), (1, 'No Risk'), (2, 'Low Risk'), (4, 'Medium Risk'), (8, 'High Risk'), (16, 'Critical Risk')], db_index=True, default=0, editable=False),
        ),
        migrations.CreateModel(
            name='Vulnerability',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pkgname', models.CharField(editable=False, max_length=128)),
                ('installedversion', models.CharField(editable=False, max_length=128)),
                ('vulnerabilityid', models.CharField(editable=False, max_length=128)),
                ('severity', models.SmallIntegerField(choices=[(2, 'Low'), (4, 'Medium'), (8, 'High'), (16, 'Critical')], db_index=True, editable=False)),
                ('severitysource', models.CharField(editable=False, max_length=64, null=True)),
                ('description', models.CharField(editable=False, max_length=1024, null=True)),
                ('fixedversion', models.CharField(editable=False, max_length=128, null=True)),
                ('publisheddate', models.CharField(editable=False, max_length=64, null=True)),
                ('lastmodifieddate', models.CharField(editable=False, max_length=64, null=True)),
                ('scan_result', django.contrib.postgres.fields.jsonb.JSONField(editable=False, null=True)),
                ('os', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name='vulnerabilities', to='rancher.OperatingSystem')),
            ],
            options={
                'ordering': ['os', 'pkgname', 'installedversion', 'vulnerabilityid'],
                'unique_together': {('os', 'pkgname', 'installedversion', 'vulnerabilityid')},
            },
        ),
        migrations.AddField(
            model_name='containerimage',
            name='vulnerabilities',
            field=models.ManyToManyField(to='rancher.Vulnerability'),
        ),
    ]
