'''
Models for restless to store app links & tests::

    Copyright (C) 2011 Department of Environment & Conservation

    Authors:
     * Adon Metcalfe
     * Ashley Felton

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

# Template django settings for DEC
import socket, os, django, re
SITE_ROOT = os.path.sep.join(os.path.dirname(os.path.realpath(__file__)).split(os.path.sep)[:-1])
from django.conf import settings

# Celery message broker settings
BROKER_HOST = "localhost"
BROKER_PORT = 5672
BROKER_VHOST = "local"
BROKER_USER = "local"
BROKER_PASSWORD = "local"
celeryqueue = os.path.basename(SITE_ROOT)
CELERY_QUEUES = {celeryqueue: {"exchange": celeryqueue, "binding_key": celeryqueue}}
CELERY_DEFAULT_QUEUE = celeryqueue
CELERY_TASK_TIME_LIMIT = 3600
CELERY_TASK_SOFT_TIME_LIMIT = 1800
CELERY_DISABLE_RATE_LIMITS = True

# Set port suffix for deployment with apache/nginx 
SITE_PORT = SITE_ROOT.split("_")[-1]

# setup gdal if it hasn't been correctly autodetected
from django.contrib.gis import gdal
if gdal.HAS_GDAL == False:
    GDAL_LIBRARY_PATH = '/usr/lib/python2.6/dist-packages/osgeo/_gdal.so'
    reload(gdal)

HOSTNAME = socket.gethostname()

from django.utils.http import urlquote
# Build a unique sitename for this app to use when making service requests
SITE_NAME = urlquote(os.path.basename(SITE_ROOT) + "/" + HOSTNAME)

SESSION_COOKIE_NAME = SITE_NAME.replace("/", "|").encode("ascii")

# Setup directories for content
TEMPLATE_DIRS = (
    os.path.join(SITE_ROOT, 'templates'), 
    os.path.join(SITE_ROOT, 'restless', 'templates'),
    os.path.join(SITE_ROOT, 'dec_base', 'templates')
)
STATICFILES_DIRS = (os.path.join(SITE_ROOT, 'static'), )
# The 3 root directories are automatically served with nginx in front of apache, unsecured, no indexes
# To avoid fuzzing attacks pass secured assets through a view
MEDIA_ROOT = os.path.join(SITE_ROOT, 'media')
STATIC_ROOT = os.path.join(SITE_ROOT,"static_files/{0}".format(os.path.basename(SITE_ROOT)))
try: os.makedirs(STATIC_ROOT)
except: pass
MEDIA_URL = '/media/'
STATIC_URL = '/static/'
#ADMIN_MEDIA_PREFIX = '/static/admin/'

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = False
TIME_ZONE = 'Australia/Perth'
LANGUAGE_CODE = 'en-us'
SITE_ID = 1

ROOT_URLCONF = 'urls'

MIDDLEWARE_CLASSES = (
    'django.middleware.gzip.GZipMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'reversion.middleware.RevisionMiddleware',
    'restless.middleware.AuthenticationMiddleware',
    'django.contrib.redirects.middleware.RedirectFallbackMiddleware'
)

TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
    'django.core.context_processors.media',
    'django.core.context_processors.request',
    'django.core.context_processors.csrf',
    'django.core.context_processors.static'
)

INSTALLED_APPS = (
    # Django includes
    'django.contrib.admin',
    'django.contrib.admindocs',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.gis',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'django.contrib.redirects',
    'django.contrib.sites',
    # Standard includes
    'treebeard', # Hierarchical model helpers
    'taggit', # Tagging
    'uni_form', # More accessible forms
    'tinymce', # Provides a WYSIWYG textfield editor
    'reversion', # Provides version control for models
    'djcelery', # Scheduled & async tasks
    'restless', # The bees knees =)
    'dec_base', # Templates for standard DEC apps
    #'dec_base.example_app', # Example DEC application
)

CACHES = {
    'mem': {
        'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
        'LOCATION': 'localhost:11211',
        'OPTIONS': {
            'MAX_ENTRIES': 1000000,
            'CULL_FREQUENCY': 2
        },
        'KEY_PREFIX': os.path.basename(SITE_ROOT)
    },
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'django_cache',
        'OPTIONS': {
            'MAX_ENTRIES': 50000,
            'CULL_FREQEUNCY': 2
        }
    },
    'file': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.path.join(MEDIA_ROOT, 'django_cache'),
        'OPTIONS': {
            'MAX_ENTRIES': 1000000,
        }
    }
}

DEBUG_MIDDLEWARE_CLASSES = (
    'debug_toolbar.middleware.DebugToolbarMiddleware',
)

DEBUG_INSTALLED_APPS = (
    # Development includes
    'debug_toolbar',
)

def show_debug_toolbar(request):
    if request.GET.has_key("debug"): return settings.DEBUG

DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': show_debug_toolbar,
    'INTERCEPT_REDIRECTS': False,
    'HIDE_DJANGO_SQL': False,
    #'TAG': 'div',
}

DEBUG_TOOLBAR_PANELS = (
    'debug_toolbar.panels.version.VersionDebugPanel',
    'debug_toolbar.panels.timer.TimerDebugPanel',
    'debug_toolbar.panels.settings.SettingsPanel',
    'debug_toolbar.panels.headers.HeaderDebugPanel',
    'debug_toolbar.panels.request_vars.RequestVarsDebugPanel',
    'debug_toolbar.panels.template.TemplateDebugPanel',
    'debug_toolbar.panels.sql.SQLDebugPanel',
    'debug_toolbar.panels.signals.SignalDebugPanel',
    'debug_toolbar.panels.logging.LoggingPanel'
)

LOGGING = {
    'version': 1,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
        'database': {
            'format': '%(levelname)s %(asctime)s %(module)s %(param)s %(duration)d %(sql)s %(message)s'
        }
    },
    'handlers': {
        'file':{
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(MEDIA_ROOT, "django.log"),
            'formatter': 'verbose',
            'maxBytes': '16777216'
        },
        'mail-admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['file', 'mail-admins'],
            'level': 'INFO'
        }, 
        'log': {
            'handlers': ['file'],
            'level': 'INFO'
        }, 
    }
}

DEBUG_LOGGING = {
    'version': 1,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
        'database': {
            'format': '%(levelname)s %(asctime)s %(module)s %(param)s %(duration)d %(sql)s %(message)s'
        }
    },
    'handlers': {
        'file':{
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(MEDIA_ROOT, "django.log"),
            'formatter': 'verbose',
            'maxBytes': '16777216'
        },
        'db':{
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(MEDIA_ROOT, "djangodb.log"),
            'formatter': 'verbose',
            'maxBytes': '16777216'
        },
    },
    'loggers': {
        'django_auth_ldap': {
            'handlers': ['file'],
            'level': 'DEBUG'
        }, 
        'django.request': {
            'handlers': ['file'],
            'level': 'DEBUG'
        }, 
        'django.db.backends.disabled': {
            'handlers': ['db'],
            'level': 'DEBUG'
        }, 
        'log': {
            'handlers': ['file'],
            'level': 'DEBUG'
        }, 
    }
}

# TinyMCE settings
TINYMCE_JS_URL = STATIC_URL + 'js/tiny_mce/tiny_mce.js'
TINYMCE_JS_ROOT = STATIC_URL + 'js/tiny_mce'
TINYMCE_DEFAULT_CONFIG = {'theme':'simple', 'relative_urls':False}

# Email settings
EMAIL_HOST = 'alerts.corporateict.domain'
EMAIL_PORT = 25

# Set debug flag if hostname contains dev
if True or os.path.exists(os.path.join(SITE_ROOT, "debug")):
    DEBUG = True
    LOGGING = DEBUG_LOGGING
else:
    DEBUG = False

if DEBUG:
    MIDDLEWARE_CLASSES += DEBUG_MIDDLEWARE_CLASSES
    INSTALLED_APPS += DEBUG_INSTALLED_APPS
else: # cache templates
    TEMPLATE_LOADERS = (('django.template.loaders.cached.Loader', TEMPLATE_LOADERS), )

# Login and redirect URLs
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_URL = '/logout/'
