"""
Base Django settings for itassets project.
"""
from confy import env, database
import os
import sys
from unipath import Path

# Project paths
# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = Path(__file__).ancestor(2)
PROJECT_DIR = os.path.join(BASE_DIR, 'itassets')
# Add BASE_DIR to the system path.
sys.path.insert(0, BASE_DIR)


# Database configuration
DATABASES = {
    # Defined in DATABASE_URL env variable.
    'default': database.config(),
}

# Settings defined in environment variables.
DEBUG = env('DEBUG', False)
SECRET_KEY = env('SECRET_KEY')
CSRF_COOKIE_SECURE = env('CSRF_COOKIE_SECURE', False)
SESSION_COOKIE_SECURE = env('SESSION_COOKIE_SECURE', False)
if not DEBUG:
    # Localhost, UAT and Production hosts
    ALLOWED_HOSTS = [
        'localhost',
        '127.0.0.1',
        'assets.dpaw.wa.gov.au',
        'assets.dpaw.wa.gov.au.',
        'assets-uat.dpaw.wa.gov.au',
        'assets-uat.dpaw.wa.gov.au.',
    ]
INTERNAL_IPS = ['127.0.0.1', '::1']
ROOT_URLCONF = 'itassets.urls'
WSGI_APPLICATION = 'itassets.wsgi.application'
INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    'reversion',
    'assets',
)
MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    #'dpaw_utils.middleware.SSOLoginMiddleware',
)
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Database configuration
DATABASES = {
    # Defined in the DATABASE_URL env variable.
    'default': database.config(),
}

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Australia/Perth'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'

# Logging settings
# Ensure that the logs directory exists:
if not os.path.exists(os.path.join(BASE_DIR, 'logs')):
    os.mkdir(os.path.join(BASE_DIR, 'logs'))
LOGGING = {
    'version': 1,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(message)s'
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'assets.log'),
            'formatter': 'verbose',
            'maxBytes': 1024 * 1024 * 5
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['file'],
            'level': 'INFO'
        },
        'log': {
            'handlers': ['file'],
            'level': 'INFO'
        },
    }
}

# Supplement some settings when DEBUG is True.
if DEBUG:
    # Developer local IP may be required for debug_toolbar to work/
    if env('INTERNAL_IP', False):
        INTERNAL_IPS.append(env('INTERNAL_IP'))
    INSTALLED_APPS += (
        'debug_toolbar',
    )
    DEBUG_TOOLBAR_PATCH_SETTINGS = True
    MIDDLEWARE_CLASSES = ('debug_toolbar.middleware.DebugToolbarMiddleware',) + MIDDLEWARE_CLASSES
