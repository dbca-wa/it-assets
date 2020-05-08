import importlib
import os

from django.conf import settings


def _import_synctask():
    table_name = settings.ALESCO_DB_TABLE
    if "." in table_name:
        table_name = os.path.splitext(table_name)[1][1:]
    return importlib.import_module("organisation.alesco.{}".format(table_name))

synctask = _import_synctask()




