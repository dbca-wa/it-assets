# Generated by Django 2.2.16 on 2020-10-09 02:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registers', '0031_auto_20200909_1155'),
    ]

    operations = [
        migrations.AddField(
            model_name='changerequest',
            name='initiative_name',
            field=models.CharField(blank=True, help_text='Tactical roadmap initiative name', max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='changerequest',
            name='initiative_no',
            field=models.CharField(blank=True, help_text='Tactical roadmap initiative number', max_length=255, null=True, verbose_name='initiative no.'),
        ),
        migrations.AddField(
            model_name='changerequest',
            name='project_no',
            field=models.CharField(blank=True, help_text='Project number (if applicable)', max_length=255, null=True, verbose_name='project no.'),
        ),
    ]
