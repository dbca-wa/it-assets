# Generated by Django 2.2.14 on 2020-07-21 03:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('status', '0009_auto_20200218_0745'),
    ]

    operations = [
        migrations.AlterField(
            model_name='host',
            name='name',
            field=models.CharField(max_length=256, unique=True),
        ),
    ]
