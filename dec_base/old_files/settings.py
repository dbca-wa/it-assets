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
SESSION_ENGINE = 'redis_sessions.session'

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
STATIC_ROOT = os.path.join("/var/www/django_static/{0}".format(os.path.basename(SITE_ROOT)))
try: os.makedirs(STATIC_ROOT)
except: pass
MEDIA_URL = '/media/'
STATIC_URL = '/static/'
DEC_CDN = '//ge.dec.wa.gov.au/_/'
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = False
USE_TZ = True
TIME_ZONE = 'Australia/Perth'
LANGUAGE_CODE = 'en-us'
SITE_ID = 1

ROOT_URLCONF = 'urls'

PASSWORD_HASHERS = (
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptPasswordHasher',
    'django.contrib.auth.hashers.SHA1PasswordHasher',
    'django.contrib.auth.hashers.MD5PasswordHasher',
    'django.contrib.auth.hashers.CryptPasswordHasher',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    #'django.middleware.transaction.TransactionMiddleware',
    'reversion.middleware.RevisionMiddleware',
    'pagination.middleware.PaginationMiddleware',
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
    #'django.contrib.markup',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'django.contrib.redirects',
    'django.contrib.sites',
    # Standard includes
    'django_extensions', # shell_plus extension, amongst other things.
    'pagination', # Nice pagination template tags.
    'bootstrap_pagination', # Plays nice with Bootstrap pagination styles.
    'taggit', # Tagging
    'uni_form', # More accessible forms
    'crispy_forms', # Successor to uni_form.
    'floppyforms', # Another great forms app
    'tinymce', # Provides a WYSIWYG textfield editor
    'reversion', # Provides version control for models
    'djcelery', # Delayed task execution & schedulinh
    'restless', # The bees knees =) (Audit ++)
    'dec_base', # Templates for standard DEC apps
    #'dec_base.example_app', # Example DEC application
)

BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis"
CELERY_REDIS_HOST = "localhost"
CELERY_REDIS_PORT = 6379
CELERY_REDIS_DB = 2
import djcelery
djcelery.setup_loader()

CACHES = {
    'default': {
        'BACKEND': 'redis_cache.cache.RedisCache',
        'LOCATION': 'localhost:6379',
        'OPTIONS': {
            'DB': 1,
        },
    },
}

DEBUG_MIDDLEWARE_CLASSES = (
    'debug_toolbar.middleware.DebugToolbarMiddleware',
)

DEBUG_INSTALLED_APPS = (
    # Development includes
    'debug_toolbar',
)

def show_debug_toolbar(request):
    if request.GET.has_key("debug"):
        request.session["debug"] = request.GET["debug"] == "on"
    elif not request.session.has_key("debug"):
        request.session["debug"] = False
    return settings.DEBUG and request.session["debug"]

DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': show_debug_toolbar,
    'INTERCEPT_REDIRECTS': False,
    'HIDE_DJANGO_SQL': False,
    #'TAG': 'div',
}

DEBUG_TOOLBAR_PANELS = (
    'debug_toolbar.panels.version.VersionDebugPanel',
    'debug_toolbar.panels.timer.TimerDebugPanel',
    'debug_toolbar.panels.settings_vars.SettingsVarsDebugPanel',
    'debug_toolbar.panels.headers.HeaderDebugPanel',
    'debug_toolbar.panels.request_vars.RequestVarsDebugPanel',
    'debug_toolbar.panels.template.TemplateDebugPanel',
    'debug_toolbar.panels.sql.SQLDebugPanel',
    'debug_toolbar.panels.signals.SignalDebugPanel',
    'debug_toolbar.panels.logger.LoggingPanel',
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
            'filename': os.path.join(MEDIA_ROOT, 'django.log'),
            'formatter': 'verbose',
            'maxBytes': '16777216'
        },
        'mail-admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'view_stats':{
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(MEDIA_ROOT, 'view_stats.log'),
            'formatter': 'verbose',
            'maxBytes': '16777216'
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
        'view_stats': {
            'handlers': ['view_stats'],
            'level': 'INFO'
        }
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
        'view_stats':{
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(MEDIA_ROOT, 'view_stats.log'),
            'formatter': 'verbose',
            'maxBytes': '16777216'
        }
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
        'view_stats': {
            'handlers': ['view_stats'],
            'level': 'INFO'
        }
    }
}

# TinyMCE settings
TINYMCE_JS_URL = STATIC_URL + 'tiny_mce/tiny_mce.js'
TINYMCE_JS_ROOT = STATIC_URL + 'tiny_mce'
TINYMCE_DEFAULT_CONFIG = {
    'theme': 'advanced',
    'plugins': 'table,spellchecker,paste',
    'convert_urls': False,
}
#TINYMCE_COMPRESSOR = True  # Leave this commented out. The compressor is broken in Django>=1.2

# Email settings
EMAIL_HOST = 'alerts.corporateict.domain'
EMAIL_PORT = 25

# Set debug flag if project directory contains a file called 'debug' (case-insensitive):
project_dir = [i.upper() for i in os.listdir(SITE_ROOT)]
if 'DEBUG' in project_dir:
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

# Sensible AU date input formats
DATE_INPUT_FORMATS = (
    '%d/%m/%y',
    '%d/%m/%Y',
    '%d-%m-%y',
    '%d-%m-%Y',
    '%d %b %Y',
    '%d %b, %Y',
    '%d %B %Y',
    '%d %B, %Y')

DATETIME_INPUT_FORMATS = [
    '%d/%m/%y %H:%M',
    '%d/%m/%Y %H:%M',
    '%d-%m-%y %H:%M',
    '%d-%m-%Y %H:%M',
]

# Add a context to all templates
def dec_base_template_context(request):
    '''Define a dictionary of context variables to pass to every template.
    '''
    # The dictionary below will be passed to all templates being rendered.
    return {
        'DEC_CDN':DEC_CDN,
        }

TEMPLATE_CONTEXT_PROCESSORS += ('settings.dec_base_template_context',)
