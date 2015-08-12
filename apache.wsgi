import os
BASEDIR = os.path.dirname(os.path.realpath(__file__))

# Cool virtualenv integration
activate_this = os.path.join(BASEDIR, 'virtualenv/bin/activate_this.py')
execfile(activate_this, dict(__file__=activate_this))

import sys
sys.path.append(BASEDIR)
sys.stdout = sys.stderr
os.environ["DJANGO_SETTINGS_MODULE"] = "settings"

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()
