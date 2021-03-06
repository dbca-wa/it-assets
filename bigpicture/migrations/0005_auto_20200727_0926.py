# Generated by Django 2.2.14 on 2020-07-27 01:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bigpicture', '0004_auto_20200722_1413'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dependency',
            name='health',
        ),
        migrations.AlterField(
            model_name='dependency',
            name='category',
            field=models.CharField(choices=[('Service', 'Service'), ('Compute', 'Compute'), ('Storage', 'Storage'), ('Proxy target', 'Proxy target')], help_text='The category of this dependency.', max_length=64),
        ),
        migrations.AlterField(
            model_name='riskassessment',
            name='category',
            field=models.CharField(choices=[('Critical function', 'Critical function'), ('Traffic', 'Traffic'), ('Access', 'Access'), ('Backups', 'Backups'), ('Support', 'Support'), ('Operating System', 'Operating System'), ('Vulnerability', 'Vulnerability'), ('Contingency plan', 'Contingency plan')], help_text='The category which this risk falls into.', max_length=64),
        ),
    ]
