# Generated by Django 2.2.14 on 2020-08-10 02:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nginx', '0004_auto_20200806_0837'),
    ]

    operations = [
        migrations.AlterField(
            model_name='requestpathnormalizer',
            name='order',
            field=models.PositiveSmallIntegerField(default=1, help_text='The order to find the filter rule, high order means hight priority'),
        ),
    ]
