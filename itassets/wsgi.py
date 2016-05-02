"""
WSGI config for itassets project.
It exposes the WSGI callable as a module-level variable named ``application``.
"""
import confy
confy.read_environment_file('.env')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
