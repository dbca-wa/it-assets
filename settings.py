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

 
# Database configuration

DATABASES = {
    'default': {
        'NAME':'assets_8208',
        'HOST':'localhost',
        'PORT':'5432',
        'USER':'postgres',
        'PASSWORD':'postgres',
        'ENGINE':'django.contrib.gis.db.backends.postgis',
    },
}


# Standard DEC settings template imported from dec_base
# pulls settings from dec_base/settings.py and dec_base/authentication.py
from dec_base import defaults; defaults(exclude=['AUTH_LDAP_USER_FLAGS_BY_GROUP'])

'''
----------------------------
Custom settings beneath here
----------------------------
'''

# Make this unique, and don't share it with anybody.
# Use ./manage.py generate_secret_key after cloning this project.
SECRET_KEY = '7e8964cebd5a2c8f3cb402337a05c8b5c92cd266c252bd8c1ca003c41a3443f4'

DEBUG = True if os.environ.get('DEBUG', False) == 'True' else False

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

ADMIN_MEDIA_PREFIX='/static/'

# Login to the admin
LOGIN_URL = "/admin"
