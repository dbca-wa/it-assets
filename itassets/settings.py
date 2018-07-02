from confy import database, env
import os
import sys
from unipath import Path

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = Path(__file__).ancestor(2)
PROJECT_DIR = os.path.join(BASE_DIR, 'itassets')
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
    'django.contrib.staticfiles',
    'django_extensions',
    'raven.contrib.django.raven_compat',
    'reversion',
    'mptt',
    'django_mptt_admin',
    'leaflet',
    #'django_q',
    'organisation',
    'registers',
    'tracking',
    'assets',
    'webconfig',
    'knowledge',
)
MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'dpaw_utils.middleware.SSOLoginMiddleware',
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
APPLICATION_VERSION_NO = '2.0.3'
ADMINS = ('asi@dbca.wa.gov.au',)
API_RESPONSE_CACHE_SECONDS = env('API_RESPONSE_CACHE_SECONDS', None)
FRESHDESK_ENDPOINT = env('FRESHDESK_ENDPOINT', None)
FRESHDESK_API_KEY = env('FRESHDESK_API_KEY', None)
AWS_JSON_PATH = env('AWS_JSON_PATH', None)


# Database configuration
DATABASES = {
    # Defined in DATABASE_URL env variable.
    'default': database.config(),
}


# Static files configuration
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'
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
    '%d/%m/%y',
    '%d/%m/%Y',
    '%d-%m-%y',
    '%d-%m-%Y',
    '%d %b %Y',
    '%d %b, %Y',
    '%d %B %Y',
    '%d %B, %Y')
DATETIME_INPUT_FORMATS = (
    '%d/%m/%y %H:%M',
    '%d/%m/%Y %H:%M',
    '%d-%m-%y %H:%M',
    '%d-%m-%Y %H:%M',)


# Email settings.
EMAIL_HOST = env('EMAIL_HOST', 'email.host')
EMAIL_PORT = env('EMAIL_PORT', 25)


# Logging settings
# Ensure that the logs directory exists:
if not os.path.exists(os.path.join(BASE_DIR, 'logs')):
    os.mkdir(os.path.join(BASE_DIR, 'logs'))
LOGGING = {
    'version': 1,
    'formatters': {
        'console': {'format': '%(levelname)s %(message)s'},
        'simple': {'format': '%(levelname)s %(asctime)s %(message)s'},
        'verbose': {'format': '%(levelname)s %(asctime)s %(module)s %(message)s'},
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'console'
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'itassets.log'),
            'formatter': 'simple',
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 5,
        },
		'sentry': {
            'level': 'WARNING',
            'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
			'propagate': True,
        },
        'django.request': {
            'handlers': ['console', 'sentry'],
            'level': 'ERROR',
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


# django-q configuration
Q_CLUSTER = {
    'name': 'itassets',
    'workers': 4,
    'recycle': 500,
    'timeout': 180,
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
if env('RAVEN_DSN', False):
    RAVEN_CONFIG = {'dsn': env('RAVEN_DSN')}
