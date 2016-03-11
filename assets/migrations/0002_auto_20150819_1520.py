# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='model',
            name='lifecycle',
            field=models.IntegerField(help_text='Enter in years how long we should keep items of this model before they get decomissioned. Desktops should generally be three years, servers and networking equipment five years.'),
        ),
    ]
