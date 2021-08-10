# Generated by Django 2.2.24 on 2021-08-08 23:49

import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('rancher', '0038_manual_20210727_0957'),
    ]

    operations = [
        migrations.CreateModel(
            name='Secret',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted', models.DateTimeField(db_index=True, editable=False, null=True)),
                ('name', models.CharField(editable=False, max_length=128)),
                ('api_version', models.CharField(editable=False, max_length=64)),
                ('modified', models.DateTimeField(editable=False)),
                ('created', models.DateTimeField(editable=False)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name_plural': '          Secrets',
                'ordering': ['cluster__name', 'project', 'name'],
            },
        ),
        migrations.AlterModelOptions(
            name='cluster',
            options={'ordering': ['name'], 'verbose_name_plural': '             Clusters'},
        ),
        migrations.AlterModelOptions(
            name='configmap',
            options={'ordering': ['cluster__name', 'namespace__name', 'name'], 'verbose_name_plural': '         Config maps'},
        ),
        migrations.AlterModelOptions(
            name='containerimage',
            options={'ordering': ['imagefamily__account', 'imagefamily__name', 'tag'], 'verbose_name_plural': '   Images'},
        ),
        migrations.AlterModelOptions(
            name='containerimagefamily',
            options={'ordering': ['account', 'name'], 'verbose_name_plural': '    Image Families'},
        ),
        migrations.AlterModelOptions(
            name='envscanmodule',
            options={'ordering': ['-priority'], 'verbose_name_plural': '              Env Scan Modules'},
        ),
        migrations.AlterModelOptions(
            name='namespace',
            options={'ordering': ['cluster__name', 'name'], 'verbose_name_plural': '           Namespaces'},
        ),
        migrations.AlterModelOptions(
            name='operatingsystem',
            options={'ordering': ['name', 'version'], 'verbose_name_plural': '      OperatingSystems'},
        ),
        migrations.AlterModelOptions(
            name='persistentvolume',
            options={'ordering': ['cluster__name', 'name'], 'verbose_name_plural': '        Persistent volumes'},
        ),
        migrations.AlterModelOptions(
            name='project',
            options={'ordering': ['cluster__name', 'name'], 'verbose_name_plural': '            Projects'},
        ),
        migrations.AlterModelOptions(
            name='vulnerability',
            options={'ordering': ['severity', 'pkgname', 'installedversion', 'vulnerabilityid'], 'verbose_name_plural': '     Vulnerabilities'},
        ),
        migrations.AlterModelOptions(
            name='workload',
            options={'ordering': ['cluster__name', 'namespace', 'name'], 'verbose_name_plural': '       Workloads'},
        ),
        migrations.AlterModelOptions(
            name='workloadresource',
            options={'ordering': ['imagefamily', 'workload', 'resource_type', 'config_items'], 'verbose_name_plural': '  Workload Resources'},
        ),
        migrations.RemoveField(
            model_name='containerimagefamily',
            name='resource_scan_issues',
        ),
        migrations.RemoveField(
            model_name='containerimagefamily',
            name='resource_scaned',
        ),
        migrations.RemoveField(
            model_name='workloadvolume',
            name='other_config_old',
        ),
        migrations.AddField(
            model_name='configmap',
            name='deleted',
            field=models.DateTimeField(db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='namespace',
            name='system_namespace',
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddField(
            model_name='workload',
            name='dependency_changed',
            field=models.DateTimeField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='workload',
            name='dependency_scan_requested',
            field=models.DateTimeField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='workload',
            name='resource_changed',
            field=models.DateTimeField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='workloaddependenttree',
            name='restree_update_requested',
            field=models.DateTimeField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='workloaddependenttree',
            name='wltree_update_requested',
            field=models.DateTimeField(editable=False, null=True),
        ),
        migrations.AlterField(
            model_name='containerimage',
            name='imagefamily',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name='containerimages', to='rancher.ContainerImageFamily'),
        ),
        migrations.AlterField(
            model_name='envscanmodule',
            name='resource_type',
            field=models.PositiveSmallIntegerField(choices=[(20, 'Databases'), (21, 'Postgres'), (22, 'Oracle'), (23, 'MySQL'), (1, 'File System'), (2, 'Blob Storage'), (3, 'REST Api'), (4, 'Email Server'), (11, 'Memcached'), (12, 'Redis'), (999, 'Services')]),
        ),
        migrations.AlterField(
            model_name='workload',
            name='containerimage',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name='workloadset', to='rancher.ContainerImage'),
        ),
        migrations.AlterField(
            model_name='workloaddependency',
            name='del_dependent_workloads',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(editable=False), db_index=True, size=None),
        ),
        migrations.AlterField(
            model_name='workloaddependency',
            name='dependent_workloads',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(editable=False), db_index=True, size=None),
        ),
        migrations.AlterUniqueTogether(
            name='containerimage',
            unique_together={('imagefamily', 'tag')},
        ),
        migrations.CreateModel(
            name='SecretItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(editable=False, max_length=128)),
                ('value', models.TextField(editable=False, max_length=1024, null=True)),
                ('modified', models.DateTimeField(editable=False)),
                ('created', models.DateTimeField(editable=False)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('secret', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.CASCADE, related_name='items', to='rancher.Secret')),
            ],
            options={
                'ordering': ['secret', 'name'],
                'unique_together': {('secret', 'name')},
            },
        ),
        migrations.AddField(
            model_name='secret',
            name='cluster',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name='secrets', to='rancher.Cluster'),
        ),
        migrations.AddField(
            model_name='secret',
            name='namespace',
            field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='secrets', to='rancher.Namespace'),
        ),
        migrations.AddField(
            model_name='secret',
            name='project',
            field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='secrets', to='rancher.Project'),
        ),
        migrations.RemoveField(
            model_name='containerimage',
            name='account',
        ),
        migrations.RemoveField(
            model_name='containerimage',
            name='name',
        ),
        migrations.AddField(
            model_name='workloadenv',
            name='secret',
            field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='workloadenvs', to='rancher.Secret'),
        ),
        migrations.AddField(
            model_name='workloadenv',
            name='secretitem',
            field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='workloadenvs', to='rancher.SecretItem'),
        ),
        migrations.AlterUniqueTogether(
            name='secret',
            unique_together={('cluster', 'project', 'name')},
        ),
    ]
