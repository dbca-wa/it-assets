# Generated by Django 2.0.9 on 2019-01-04 03:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registers', '0013_auto_20181221_0954'),
    ]

    operations = [
        migrations.AddField(
            model_name='standardchange',
            name='implementation',
            field=models.TextField(blank=True, help_text='Implementation/deployment instructions', null=True),
        ),
        migrations.AddField(
            model_name='standardchange',
            name='implementation_docs',
            field=models.FileField(blank=True, help_text='Implementation/deployment instructions (attachment)', null=True, upload_to='uploads/%Y/%m/%d'),
        ),
    ]
