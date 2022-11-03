from dbca_utils.utils import env
import dj_database_url
import os
import sys
from pathlib import Path
from datetime import timedelta

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = str(Path(__file__).resolve().parents[1])
PROJECT_DIR = str(Path(__file__).resolve().parents[0])
# Add PROJECT_DIR to the system path.
sys.path.insert(0, PROJECT_DIR)

# Settings defined in environment variables.
DEBUG = env('DEBUG', False)
SECRET_KEY = env('SECRET_KEY', 'PlaceholderSecretKey')
CSRF_COOKIE_SECURE = env('CSRF_COOKIE_SECURE', False)
CSRF_COOKIE_HTTPONLY = env('CSRF_COOKIE_HTTPONLY', False)
SESSION_COOKIE_SECURE = env('SESSION_COOKIE_SECURE', False)
if not DEBUG:
    ALLOWED_HOSTS = env('ALLOWED_DOMAINS', '').split(',')
else:
    ALLOWED_HOSTS = ['*']
INTERNAL_IPS = ['127.0.0.1', '::1']
ROOT_URLCONF = 'itassets.urls'
WSGI_APPLICATION = 'itassets.wsgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

INSTALLED_APPS = (
    'whitenoise.runserver_nostatic',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django_json_widget',
    # Third-party applications:
    'django_extensions',
    'crispy_forms',
    'webtemplate_dbca',
    'bootstrap_pagination',
    'markdownx',
    # Project applications:
    'organisation',
    'registers',
    'nginx',
    'rancher',
    'bigpicture',
)

MIDDLEWARE = [
    'itassets.middleware.HealthCheckMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'csp.middleware.CSPMiddleware',
    'dbca_utils.middleware.SSOLoginMiddleware',
]

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
                'itassets.context_processors.from_settings',
            ],
        },
    }
]

ADMIN_EMAILS = env('ADMIN_EMAILS', 'asi@dbca.wa.gov.au').split(',')
SERVICE_DESK_EMAIL = env('SERVICE_DESK_EMAIL', 'oim.servicedesk@dbca.wa.gov.au')
API_RESPONSE_CACHE_SECONDS = env('API_RESPONSE_CACHE_SECONDS', 60)
FRESHSERVICE_ENDPOINT = env('FRESHSERVICE_ENDPOINT', None)
FRESHSERVICE_API_KEY = env('FRESHSERVICE_API_KEY', None)
# The FreshService hardcoded values below shouldn't ever change, but allow them to be overridden.
FRESHSERVICE_IT_SYSTEM_ASSET_TYPE_ID = env('FRESHSERVICE_IT_SYSTEM_ASSET_TYPE_ID', 75000295285)
FRESHSERVICE_NETWORK_CLIENT_ASSET_TYPE_ID = env('FRESHSERVICE_NETWORK_CLIENT_ASSET_TYPE_ID', 75000346887)
FRESHSERVICE_DEVICE_ASSET_TYPE_ID = env('FRESHSERVICE_DEVICE_ASSET_TYPE_ID', 75000295286)
MERAKI_API_KEY = env('MERAKI_API_KEY', None)
SITE_ID = 1
ENVIRONMENT_NAME = env('ENVIRONMENT_NAME', '')
ENVIRONMENT_COLOUR = env('ENVIRONMENT_COLOUR', '')
VERSION_NO = '2.3.61'
# Hardcoded Microsoft SKU ID values; these shouldn't ever change, but just it case.
# See also the DepartmentUser.MS_LICENCE_SKUS for other SKU product names.
M365_E5_SKU = '06ebc4ee-1bb5-47dd-8120-11324bc54e06'
M365_F3_SKU = '66b55226-6b4f-492c-910c-a3b7a3c9d993'
LICENCE_NOTIFY_THRESHOLD = env('LICENCE_NOTIFY_THRESHOLD', 5)

# Flag to control whether Azure AD accounts should be deactivated during sync
# processes if their associated job in Ascender has a termination date in the past.
ASCENDER_DEACTIVATE_EXPIRED = env('ASCENDER_DEACTIVATE_EXPIRED', False)
# Flag to control whether new Azure AD accounts should be created during sync.
ASCENDER_CREATE_AZURE_AD = env('ASCENDER_CREATE_AZURE_AD', False)
# Flag to set how many days ahead of their start date a new AD account should be created.
# False == no limit. Value should be an integer value.
ASCENDER_CREATE_AZURE_AD_LIMIT_DAYS = env('ASCENDER_CREATE_AZURE_AD_LIMIT_DAYS', -1)

# Settings related to the Ascender SFTP target
ASCENDER_SFTP_HOST = env('ASCENDER_SFTP_HOST', None)
ASCENDER_SFTP_PORT = env('ASCENDER_SFTP_PORT', 22)
ASCENDER_SFTP_USERNAME = env('ASCENDER_SFTP_USERNAME', None)
ASCENDER_SFTP_PASSWORD = env('ASCENDER_SFTP_PASSWORD', None)

# Ascender database view information
FOREIGN_DB_HOST = env('FOREIGN_DB_HOST', None)
FOREIGN_DB_PORT = env('FOREIGN_DB_PORT', default=5432)
FOREIGN_DB_NAME = env('FOREIGN_DB_NAME', None)
FOREIGN_DB_USERNAME = env('FOREIGN_DB_USERNAME', None)
FOREIGN_DB_PASSWORD = env('FOREIGN_DB_PASSWORD', None)
FOREIGN_SERVER = env('FOREIGN_SERVER', None)
FOREIGN_SCHEMA = env('FOREIGN_SCHEMA', default='public')
FOREIGN_TABLE = env('FOREIGN_TABLE', None)
FOREIGN_TABLE_CC_MANAGER = env('FOREIGN_TABLE_CC_MANAGER', None)

RESOURCE_CLIENTID = env("RESOURCE_CLIENTID", None)

NGINX_STORAGE_CONNECTION_STRING = env("NGINX_STORAGE_CONNECTION_STRING", None)
NGINX_CONTAINER = env("NGINX_CONTAINER", None)
NGINX_RESOURCE_NAME = env("NGINX_RESOURCE_NAME", None)

RANCHER_STORAGE_CONNECTION_STRING = env("RANCHER_STORAGE_CONNECTION_STRING", None)
RANCHER_CONTAINER = env("RANCHER_CONTAINER", None)
RANCHER_RESOURCE_NAME = env("RANCHER_RESOURCE_NAME", None)
RANCHER_MANAGEMENT_URL = env("RANCHER_MANAGEMENT_URL", default="https://rks.dbca.wa.gov.au")
RANCHER_MAX_CONSUME_TIME = env("RANCHER_MAX_CONSUME_TIME", default=3000)

CLUSTERS_MANAGEMENT_URL = {}


def GET_CLUSTER_MANAGEMENT_URL(clustername):
    if clustername not in CLUSTERS_MANAGEMENT_URL:
        CLUSTERS_MANAGEMENT_URL[clustername] = env(clustername.upper(), default=RANCHER_MANAGEMENT_URL.format(clustername))
    return CLUSTERS_MANAGEMENT_URL[clustername]


NGINXLOG_REPOSITORY_DIR = env("NGINXLOG_REPOSITORY_DIR", None)
NGINXLOG_RESOURCE_NAME = env("NGINXLOG_RESOURCE_NAME", None)
NGINXLOG_MAX_SAVED_CONSUMED_RESOURCES = env("NGINXLOG_MAX_SAVED_CONSUMED_RESOURCES", default=240)
NGINXLOG_MAX_CONSUME_TIME_PER_LOG = env("NGINXLOG_MAX_CONSUME_TIME_PER_LOG", default=3000)
NGINXLOG_STREAMING_PARSE = env("NGINXLOG_STREAMING_PARSE", True)
NGINXLOG_ACCESSLOG_LIFETIME = env('NGINXLOG_ACCESSLOG_LIFETIME', 90)
NGINXLOG_ACCESSDAILYLOG_LIFETIME = env('NGINXLOG_ACCESSDAILYLOG_LIFETIME', 180)

PODSTATUS_REPOSITORY_DIR = env("PODSTATUS_REPOSITORY_DIR", None)
PODSTATUS_RESOURCE_NAME = env("PODSTATUS_RESOURCE_NAME", None)
PODSTATUS_MAX_SAVED_CONSUMED_RESOURCES = env("PODSTATUS_MAX_SAVED_CONSUMED_RESOURCES", default=240)
PODSTATUS_MAX_CONSUME_TIME_PER_LOG = env("PODSTATUS_MAX_CONSUME_TIME_PER_LOG", default=1800)
PODSTATUS_STREAMING_PARSE = env("PODSTATUS_STREAMING_PARSE", True)

CONTAINERSTATUS_REPOSITORY_DIR = env("CONTAINERSTATUS_REPOSITORY_DIR", None)
CONTAINERSTATUS_RESOURCE_NAME = env("CONTAINERSTATUS_RESOURCE_NAME", None)
CONTAINERSTATUS_MAX_SAVED_CONSUMED_RESOURCES = env("CONTAINERSTATUS_MAX_SAVED_CONSUMED_RESOURCES", default=240)
CONTAINERSTATUS_MAX_CONSUME_TIME_PER_LOG = env("CONTAINERSTATUS_MAX_CONSUME_TIME_PER_LOG", default=1800)
CONTAINERSTATUS_STREAMING_PARSE = env("CONTAINERSTATUS_STREAMING_PARSE", True)

CONTAINERLOG_REPOSITORY_DIR = env("CONTAINERLOG_REPOSITORY_DIR", None)
CONTAINERLOG_RESOURCE_NAME = env("CONTAINERLOG_RESOURCE_NAME", None)
CONTAINERLOG_MAX_SAVED_CONSUMED_RESOURCES = env("CONTAINERLOG_MAX_SAVED_CONSUMED_RESOURCES", default=240)
CONTAINERLOG_MAX_CONSUME_TIME_PER_LOG = env("CONTAINERLOG_MAX_CONSUME_TIME_PER_LOG", default=1800)
CONTAINERLOG_STREAMING_PARSE = env("CONTAINERLOG_STREAMING_PARSE", True)
CONTAINERLOG_FAILED_IF_CONTAINER_NOT_FOUND = env("CONTAINERLOG_FAILED_IF_CONTAINER_NOT_FOUND", True)

ENABLE_ADDED_BY_CONTAINERLOG = env("ENABLE_ADDED_BY_CONTAINERLOG", False)
DELETED_RANCHER_OBJECT_EXPIRED = timedelta(days=env("DELETED_RANCHER_OBJECT_EXPIRED", 90))  # days
RANCHER_CONTAINERS_PER_WORKLOAD = env("RANCHER_CONTAINERS_PER_WORKOAD", 100)
RANCHER_CONTAINERLOG_EXPIRED = timedelta(days=env("RANCHER_CONTAINERLOG_EXPIRED", 14))  # days
RANCHER_CONTAINER_ABORTED = timedelta(days=env("RANCHER_CONTAINER_ABORTED", 2))  # days

HARVESTER_ABORTED = timedelta(seconds=env("HARVESTER_ABORTED", 3600 * 24))  # seconds
HARVESTER_EXPIRED = timedelta(days=env("HARVESTER_EXPIRED", 90))  # days

DISABLE_LOG_NOTIFICATION_EMAIL = env("DISABLE_LOG_NOTIFICATION_EMAIL", default=False)

# Database configuration
DATABASES = {
    # Defined in DATABASE_URL env variable.
    'default': dj_database_url.config(),
}


# Static files configuration
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'
STATICFILES_DIRS = (os.path.join(BASE_DIR, 'itassets', 'static'),)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
WHITENOISE_ROOT = STATIC_ROOT
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
        'console': {'format': '%(asctime)s %(levelname)-12s %(name)-12s %(message)s'},
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
            'formatter': 'console',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
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
        'azure.core.pipeline.policies.http_logging_policy': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        }
    }
}

# crispy_forms settings
CRISPY_TEMPLATE_PACK = 'bootstrap4'

# django-csp config
# Reference: https://django-csp.readthedocs.io/en/latest/configuration.html
# NOTE: add any CDN domains here where they are used to load external resources.
CSP_DEFAULT_SRC = (
    "'self'",
    "'unsafe-inline'",  # Required to allow inline styles/scripts.
    "static.dbca.wa.gov.au",
    "cdnjs.cloudflare.com",
    "cdn.jsdelivr.net",
    "code.jquery.com",
)
