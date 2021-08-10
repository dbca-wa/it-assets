# Generated by Django 2.2.24 on 2021-07-27 01:50

import django.contrib.postgres.fields
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion
import rancher.models


class Migration(migrations.Migration):

    dependencies = [
        ('rancher', '0036_workload_itsystem'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContainerImageFamily',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted', models.DateTimeField(db_index=True, editable=False, null=True)),
                ('account', models.CharField(db_index=True, editable=False, max_length=64, null=True)),
                ('name', models.CharField(editable=False, max_length=128)),
                ('config', django.contrib.postgres.fields.jsonb.JSONField(default=dict)),
                ('added', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('resource_scaned', models.DateTimeField(null=True)),
                ('resource_scan_issues', models.TextField(null=True)),
            ],
            options={
                'verbose_name_plural': ' Image Families',
                'ordering': ['account', 'name'],
                'unique_together': {('account', 'name')},
            },
        ),
        migrations.CreateModel(
            name='EnvScanModule',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('resource_type', models.PositiveSmallIntegerField(choices=[(21, 'Postgres'), (22, 'Oracle'), (23, 'MySQL'), (1, 'File System'), (2, 'Blob Storage'), (3, 'REST Api'), (4, 'Email Server'), (11, 'Memcached'), (12, 'Redis'), (999, 'Services')])),
                ('priority', models.PositiveSmallIntegerField(default=0)),
                ('multi', models.BooleanField(default=False, help_text='Apply to single env variable if False; otherwise apply to all env variables')),
                ('sourcecode', models.TextField(help_text="The source code of a python module.\n    This module must declare a method 'scan' with the following requirements.\n    Parameters:\n        1. multi is False, module must contain a function 'scan(env_name,env_value)'\n        2. multi is True, module must contain a function 'scan(envs)' envs is a list of tuple(env_name,env_value)\n    Return:\n        If succeed\n            1. if multi is False, return a dictionary with key 'resource_type'\n            2. if multi is True, return a list of dictionary with keys 'resource_type' and 'env_items'\n        If failed, return None\n")),
                ('active', models.BooleanField(default=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('added', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name_plural': '           Env Scan Modules',
                'ordering': ['-priority'],
            },
            bases=(rancher.models.DbObjectMixin, models.Model),
        ),
        migrations.CreateModel(
            name='WorkloadDependency',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dependency_type', models.PositiveSmallIntegerField(choices=[(21, 'Postgres'), (22, 'Oracle'), (23, 'MySQL'), (1, 'File System'), (2, 'Blob Storage'), (3, 'REST Api'), (4, 'Email Server'), (11, 'Memcached'), (12, 'Redis'), (999, 'Image Family')], editable=False)),
                ('dependency_pk', models.IntegerField(editable=False)),
                ('dependency_id', models.CharField(editable=False, max_length=512)),
                ('dependency_display', models.CharField(editable=False, max_length=512)),
                ('dependent_workloads', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(editable=False), size=None)),
                ('del_dependent_workloads', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(editable=False), size=None)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('imagefamily', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name='dependencies', to='rancher.ContainerImageFamily')),
            ],
            options={
                'verbose_name_plural': ' Workload Dependencies',
                'ordering': ['workload', 'dependency_type', 'dependency_id'],
            },
        ),
        migrations.CreateModel(
            name='WorkloadDependentTree',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('restree', django.contrib.postgres.fields.jsonb.JSONField(editable=False, null=True)),
                ('restree_wls', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), editable=False, null=True, size=None)),
                ('restree_created', models.DateTimeField(editable=False, null=True)),
                ('restree_updated', models.DateTimeField(editable=False, null=True)),
                ('wltree', django.contrib.postgres.fields.jsonb.JSONField(editable=False, null=True)),
                ('wltree_wls', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), editable=False, null=True, size=None)),
                ('wltree_created', models.DateTimeField(editable=False, null=True)),
                ('wltree_updated', models.DateTimeField(editable=False, null=True)),
                ('imagefamily', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name='dependenttrees', to='rancher.ContainerImageFamily')),
            ],
        ),
        migrations.CreateModel(
            name='WorkloadResource',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('config_items', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(editable=False, max_length=128), size=None)),
                ('resource_type', models.PositiveSmallIntegerField(choices=[(21, 'Postgres'), (22, 'Oracle'), (23, 'MySQL'), (1, 'File System'), (2, 'Blob Storage'), (3, 'REST Api'), (4, 'Email Server'), (11, 'Memcached'), (12, 'Redis')], editable=False)),
                ('resource_id', models.CharField(db_index=True, editable=False, max_length=512)),
                ('config_source', models.PositiveSmallIntegerField(choices=[(1, 'Env'), (2, 'Workload Volume'), (3, 'Env & Workload Volume'), (4, 'Service')], editable=False)),
                ('properties', django.contrib.postgres.fields.jsonb.JSONField(default=dict)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('imagefamily', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name='resources', to='rancher.ContainerImageFamily')),
                ('scan_module', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='resources', to='rancher.EnvScanModule')),
            ],
            options={
                'verbose_name_plural': ' Workload Resources',
                'ordering': ['imagefamily', 'workload', 'resource_type', 'config_items'],
            },
        ),
        migrations.AlterIndexTogether(
            name='databaseserver',
            index_together=None,
        ),
        migrations.RemoveField(
            model_name='databaseserver',
            name='workload',
        ),
        migrations.AlterUniqueTogether(
            name='databaseuser',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='databaseuser',
            name='server',
        ),
        migrations.AlterUniqueTogether(
            name='workloaddatabase',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='workloaddatabase',
            name='database',
        ),
        migrations.RemoveField(
            model_name='workloaddatabase',
            name='user',
        ),
        migrations.RemoveField(
            model_name='workloaddatabase',
            name='workload',
        ),
        migrations.RenameField(
            model_name='configmap',
            old_name='refreshed',
            new_name='updated',
        ),
        migrations.RenameField(
            model_name='configmapitem',
            old_name='refreshed',
            new_name='updated',
        ),
        migrations.RenameField(
            model_name='ingress',
            old_name='refreshed',
            new_name='updated',
        ),
        migrations.RenameField(
            model_name='ingressrule',
            old_name='refreshed',
            new_name='updated',
        ),
        migrations.RenameField(
            model_name='namespace',
            old_name='refreshed',
            new_name='updated',
        ),
        migrations.RenameField(
            model_name='persistentvolume',
            old_name='refreshed',
            new_name='updated',
        ),
        migrations.RenameField(
            model_name='persistentvolumeclaim',
            old_name='refreshed',
            new_name='updated',
        ),
        migrations.RenameField(
            model_name='workload',
            old_name='refreshed',
            new_name='updated',
        ),
        migrations.RenameField(
            model_name='workloadenv',
            old_name='refreshed',
            new_name='updated',
        ),
        migrations.RenameField(
            model_name='workloadlistening',
            old_name='refreshed',
            new_name='updated',
        ),
        migrations.RenameField(
            model_name='workloadvolume',
            old_name='other_config',
            new_name='other_config_old',
        ),
        migrations.RenameField(
            model_name='workloadvolume',
            old_name='refreshed',
            new_name='updated',
        ),
        migrations.AddField(
            model_name='containerimage',
            name='resource_scaned',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='workload',
            name='dependency_scaned',
            field=models.DateTimeField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='workload',
            name='resource_scaned',
            field=models.DateTimeField(editable=False, null=True),
        ),
        migrations.DeleteModel(
            name='Database',
        ),
        migrations.DeleteModel(
            name='DatabaseServer',
        ),
        migrations.DeleteModel(
            name='DatabaseUser',
        ),
        migrations.DeleteModel(
            name='WorkloadDatabase',
        ),
        migrations.AddField(
            model_name='workloadresource',
            name='workload',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.CASCADE, related_name='resources', to='rancher.Workload'),
        ),
        migrations.AddField(
            model_name='workloaddependenttree',
            name='workload',
            field=models.OneToOneField(editable=False, on_delete=django.db.models.deletion.CASCADE, related_name='dependenttree', to='rancher.Workload'),
        ),
        migrations.AddField(
            model_name='workloaddependency',
            name='workload',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.CASCADE, related_name='dependencies', to='rancher.Workload'),
        ),
        migrations.AddField(
            model_name='containerimage',
            name='imagefamily',
            field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='containerimages', to='rancher.ContainerImageFamily'),
        ),
        migrations.AlterUniqueTogether(
            name='workloadresource',
            unique_together={('workload', 'resource_type', 'config_items', 'resource_id')},
        ),
        migrations.AlterUniqueTogether(
            name='workloaddependency',
            unique_together={('workload', 'dependency_type', 'dependency_pk')},
        ),
        migrations.AddField(
            model_name='workloadvolume',
            name='other_config',
            field=django.contrib.postgres.fields.jsonb.JSONField(null=True),
        ),
    ]
