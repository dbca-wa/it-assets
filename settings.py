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
import dj_database_url, os
 
# Database configuration
DATABASES = {
    # Defined in DATABASE_URL env variable.
    'default': dj_database_url.config(),
}

# Settings defined in environment variables.
SECRET_KEY = os.environ['SECRET_KEY'] if os.environ.get('SECRET_KEY', False) else 'foo'
DEBUG = True if os.environ.get('DEBUG', False) == 'True' else False
CSRF_COOKIE_SECURE = True if os.environ.get('CSRF_COOKIE_SECURE', False) == 'True' else False
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True if os.environ.get('SESSION_COOKIE_SECURE', False) == 'True' else False
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True


if not DEBUG:
    # Localhost, UAT and Production hosts
    ALLOWED_HOSTS = [
        'localhost',
        '127.0.0.1',
        'assets.dpaw.wa.gov.au',
        'assets.dpaw.wa.gov.au.',
    ]


# Standard DEC settings template imported from dec_base
# pulls settings from dec_base/settings.py and dec_base/authentication.py
from dec_base import defaults; defaults(exclude=['AUTH_LDAP_USER_FLAGS_BY_GROUP'])

'''
----------------------------
Custom settings beneath here
----------------------------
'''


MIDDLEWARE_CLASSES += (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
)

INSTALLED_APPS += (
    'django_wsgiserver',
    'assets',
)


AUTH_LDAP_USER_FLAGS_BY_GROUP = {
    "is_staff": "CN=KENS-891-ICTSC All Users,OU=ICTSC Lists,OU=ICTSC,OU=Sites,DC=corporateict,DC=domain",
}

#ADMIN_MEDIA_PREFIX='/static/'

# Login to the admin
LOGIN_URL = "/admin"
