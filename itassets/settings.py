from dbca_utils.utils import env
import dj_database_url
import os
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
ALESCO_DB_HOST = env('ALESCO_DB_HOST')
ALESCO_DB_NAME = env('ALESCO_DB_NAME')
ALESCO_DB_TABLE = env('ALESCO_DB_TABLE')
ALESCO_DB_USERNAME = env('ALESCO_DB_USERNAME')
ALESCO_DB_PASSWORD = env('ALESCO_DB_PASSWORD')



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
        'console': {'format': '%(asctime)s %(name)-12s %(message)s'},
        'verbose': {'format': '%(asctime)s %(levelname)-8s %(message)s'},
    },
    'handlers': {
        'console': {
            'level': 'INFO',
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
if env('SENTRY_DSN', ''):
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
