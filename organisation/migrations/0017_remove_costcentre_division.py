# Generated by Django 2.2.14 on 2020-09-02 02:38

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('organisation', '0016_departmentuser_alesco_data_updated'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='costcentre',
            name='division',
        ),
    ]
