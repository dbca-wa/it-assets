"""
WSGI config for itassets project.
It exposes the WSGI callable as a module-level variable named ``application``.
"""
import confy
confy.read_environment_file('.env')

from django.core.wsgi import get_wsgi_application
from dj_static import Cling
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "itassets.settings")
application = Cling(get_wsgi_application())
