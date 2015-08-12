'''
Models for dec_base to store app links & tests::

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
        'NAME':'ge_8202',
        'HOST':'pgsql-001',
        'PORT':'5433',
        'USER':'goldeneye',
        'PASSWORD':'goldeneye',
        'ENGINE':'django.contrib.gis.db.backends.postgis',
    },
    'geoserver': {
        'NAME':'geoserver_8080',
        'HOST':'pgsql-001',
        'PORT':'5433',
        'USER':'goldeneye',
        'PASSWORD':'goldeneye',
        'ENGINE':'django.contrib.gis.db.backends.postgis',
    }
}


# Standard DEC settings template imported from dec_base
# pulls settings from dec_base/settings.py and dec_base/authentication.py
from dec_base import defaults; defaults()

'''
----------------------------
Custom settings beneath here
----------------------------
'''

# Make this unique, and don't share it with anybody.
# Use ./manage.py generate_secret_key after cloning this project.
SECRET_KEY = 'yb(q^h%d$&_pr89(szi^8d4-yuh^pzj^g8il5jzrpy48u_s8^i'

INSTALLED_APPS += (
    'geoserver', # Sample DEC project with templates.
)

# Dirs which mapproxy uses to cache tiles
MAPPROXY_ROOT = os.path.join(MEDIA_ROOT, "mapproxy")
TILECACHE = os.path.join(MAPPROXY_ROOT, 'tilecache')
TILELOCKS = os.path.join(TILECACHE, 'tilelocks')
try: os.makedirs(TILELOCKS)
except: pass

APACHE_EXTRA = '''
    WSGIScriptAlias /mapproxy {0}/mapproxy/config.wsgi
    <Location /mapproxy>
        Order deny,allow
        Deny from all
        Allow from 127.0.0.1 ::1
    </Location>'''.format(MEDIA_ROOT)

GEOSERVER_URL="http://admin:geoserver@javapp-001:8080/geoserver"
