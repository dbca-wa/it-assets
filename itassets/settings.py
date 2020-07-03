from dbca_utils.utils import env
import dj_database_url
import os
import re
import sys
from pathlib import Path

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = str(Path(__file__).resolve().parents[1])
PROJECT_DIR = str(Path(__file__).resolve().parents[0])
# Add PROJECT_DIR to the system path.
sys.path.insert(0, PROJECT_DIR)

# Settings defined in environment variables.
DEBUG = env('DEBUG', False)
SECRET_KEY = env('SECRET_KEY', 'PlaceholderSecretKey')
CSRF_COOKIE_SECURE = env('CSRF_COOKIE_SECURE', False)
SESSION_COOKIE_SECURE = env('SESSION_COOKIE_SECURE', False)
if not DEBUG:
    ALLOWED_HOSTS = env('ALLOWED_DOMAINS', '').split(',')
else:
    ALLOWED_HOSTS = ['*']
INTERNAL_IPS = ['127.0.0.1', '::1']
ROOT_URLCONF = 'itassets.urls'
WSGI_APPLICATION = 'itassets.wsgi.application'
INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django_extensions',
    'corsheaders',
    'reversion',
    'crispy_forms',
    'mptt',
    'django_mptt_admin',
    'leaflet',
    'django_q',
    'rest_framework',
    'rest_framework_gis',
    'organisation',
    'registers',
    'tracking',
    'assets',
    'webconfig',
    'knowledge',
    'recoup',
    'status',
    #'helpdesk',
    #'markdown_deux',
    #'bootstrapform',
    'nginx',
    'rancher'
)
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'dbca_utils.middleware.SSOLoginMiddleware',
]
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': (os.path.join(BASE_DIR, 'itassets', 'templates'),),
        'APP_DIRS': True,
        'OPTIONS': {
            'debug': DEBUG,
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.template.context_processors.request',
                'django.template.context_processors.csrf',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    }
]
ADMINS = ('asi@dbca.wa.gov.au',)
API_RESPONSE_CACHE_SECONDS = env('API_RESPONSE_CACHE_SECONDS', None)
FRESHDESK_ENDPOINT = env('FRESHDESK_ENDPOINT', None)
FRESHDESK_API_KEY = env('FRESHDESK_API_KEY', None)
AWS_JSON_PATH = env('AWS_JSON_PATH', None)
SITE_ID = 1

# alesco binding information
FOREIGN_DB_HOST = env('FOREIGN_DB_HOST',required=False if DEBUG else True)
FOREIGN_DB_PORT = env('FOREIGN_DB_PORT',default=5432)
FOREIGN_DB_NAME = env('FOREIGN_DB_NAME',required=False if DEBUG else True)
FOREIGN_DB_USERNAME = env('FOREIGN_DB_USERNAME',required=False if DEBUG else True)
FOREIGN_DB_PASSWORD = env('FOREIGN_DB_PASSWORD',required=False if DEBUG else True)
FOREIGN_SERVER = env('FOREIGN_SERVER',required=False if DEBUG else True)
FOREIGN_SCHEMA = env('FOREIGN_SCHEMA',default='public')
FOREIGN_TABLE = env('FOREIGN_TABLE',required=False if DEBUG else True)

ALESCO_DB_SERVER=env('ALESCO_DB_SERVER',required=False if DEBUG else True)
ALESCO_DB_USER=env('ALESCO_DB_USER',required=False if DEBUG else True)
ALESCO_DB_PASSWORD=env('ALESCO_DB_PASSWORD',required=False if DEBUG else True)
ALESCO_DB_TABLE=env('ALESCO_DB_TABLE',required=False if DEBUG else True)
ALESCO_DB_SCHEMA=env('ALESCO_DB_SCHEMA',required=False if DEBUG else True)


NGINX_STORAGE_CONNECTION_STRING = env("NGINX_STORAGE_CONNECTION_STRING",required=False if DEBUG else True)
NGINX_CONTAINER = env("NGINX_CONTAINER",required=False if DEBUG else True)
NGINX_RESOURCE_NAME = env("NGINX_RESOURCE_NAME",required=False if DEBUG else True)
NGINX_RESOURCE_CLIENTID = env("NGINX_RESOURCE_CLIENTID",required=False if DEBUG else True)

RANCHER_STORAGE_CONNECTION_STRING = env("RANCHER_STORAGE_CONNECTION_STRING",required=False if DEBUG else True)
RANCHER_CONTAINER = env("RANCHER_CONTAINER",required=False if DEBUG else True)
RANCHER_RESOURCE_NAME = env("RANCHER_RESOURCE_NAME",required=False if DEBUG else True)
RANCHER_RESOURCE_CLIENTID = env("RANCHER_RESOURCE_CLIENTID",required=False if DEBUG else True)
RANCHER_MANAGEMENT_URL = env("RANCHER_MANAGEMENT_URL",default="https://rks.dbca.wa.gov.au")

# Database configuration
DATABASES = {
    # Defined in DATABASE_URL env variable.
    'default': dj_database_url.config(),
}


# Static files configuration
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'
STATICFILES_DIRS = (os.path.join(BASE_DIR, 'itassets', 'static'),)
# Ensure that the media directory exists:
if not os.path.exists(os.path.join(BASE_DIR, 'media')):
    os.mkdir(os.path.join(BASE_DIR, 'media'))
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'


# Internationalisation.
USE_I18N = False
USE_TZ = True
TIME_ZONE = 'Australia/Perth'
LANGUAGE_CODE = 'en-us'
DATE_INPUT_FORMATS = (
    '%d/%m/%Y',
    '%d/%m/%y',
    '%d-%m-%Y',
    '%d-%m-%y',
    '%d %b %Y',
    '%d %b, %Y',
    '%d %B %Y',
    '%d %B, %Y',
)
DATETIME_INPUT_FORMATS = (
    '%d/%m/%Y %H:%M',
    '%d/%m/%y %H:%M',
    '%d-%m-%Y %H:%M',
    '%d-%m-%y %H:%M',
)


# Email settings.
EMAIL_HOST = env('EMAIL_HOST', 'email.host')
EMAIL_PORT = env('EMAIL_PORT', 25)
NOREPLY_EMAIL = env('NOREPLY_EMAIL', 'noreply@dbca.wa.gov.au')


# Logging settings - log to stdout/stderr
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {'format': '%(asctime)s %(levelname)-8s %(name)-12s %(message)s'},
        'verbose': {'format': '%(asctime)s %(levelname)-8s %(message)s'},
    },
    'handlers': {
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'console'
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
			'propagate': True,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'WARNING',
			'propagate': False,
        },
        'itassets': {
            'handlers': ['console'],
            'level': 'INFO'
        },
        'sync_tasks': {
            'handlers': ['console'],
            'level': 'INFO'
        },
        'data_storage': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO'
        },
        'nginx': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO'
        },
        'rancher': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO'
        },
    }
}

# cors whitelist for local development
CORS_ORIGIN_WHITELIST = (
    'localhost:8000',
    'localhost:8080',
    '127.0.0.1:8000',
    '127.0.0.1:8080',
)

CORS_ALLOW_CREDENTIALS = True


# django-q configuration
Q_CLUSTER = {
    'name': env('REDIS_QUEUE_NAME', 'itassets'),
    'workers': 16,
    'recycle': 500,
    'timeout': 7200,
    'compress': True,
    'save_limit': 250,
    'queue_limit': 500,
    'cpu_affinity': 1,
    'label': 'Django Q',
    'redis': {
        'host': env('REDIS_HOST', 'localhost'),
        'port': 6379,
        'db': 0, }
}


# Sentry configuration
if env('SENTRY_DSN', False):
    SENTRY_CONFIG = {'dsn': env('SENTRY_DSN')}


# default REST API permissions
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    )
}

# crispy_forms settings
CRISPY_TEMPLATE_PACK = 'bootstrap3'

# status scanning settings
STATUS_NMAP_TIMEOUT = env('STATUS_NMAP_TIMEOUT', 600)
