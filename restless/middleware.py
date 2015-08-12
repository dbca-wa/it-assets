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

from __future__ import division, print_function, unicode_literals, absolute_import
import logging
logger = logging.getLogger("log."+__name__)

import threading
from re import compile
from datetime import datetime, timedelta

from django import http
from django.conf import settings

from restless.models import Token, get_locals

try:
    XS_SHARING_ALLOWED_ORIGINS = settings.XS_SHARING_ALLOWED_ORIGINS
    XS_SHARING_ALLOWED_METHODS = settings.XS_SHARING_ALLOWED_METHODS
except:
    XS_SHARING_ALLOWED_ORIGINS = '*'
    XS_SHARING_ALLOWED_METHODS = ['POST','GET','OPTIONS', 'PUT', 'DELETE']

EXEMPT_URLS = [compile(settings.LOGIN_URL.lstrip('/'))]
if hasattr(settings, 'LOGIN_EXEMPT_URLS'):
    EXEMPT_URLS += [compile(expr) for expr in settings.LOGIN_EXEMPT_URLS]

def cors_preflight_response(request, response=None):
    response = response or http.HttpResponse()
    response['Access-Control-Allow-Origin'] = XS_SHARING_ALLOWED_ORIGINS
    response['Access-Control-Allow-Methods'] = ",".join( XS_SHARING_ALLOWED_METHODS )
    if 'HTTP_ACCESS_CONTROL_REQUEST_HEADERS' in request.META:
        response['Access-Control-Allow-Headers'] = request.META["HTTP_ACCESS_CONTROL_REQUEST_HEADERS"]
    return response

class AuthenticationMiddleware(object):
    def process_request(self, request):
        if 'HTTP_ACCESS_CONTROL_REQUEST_METHOD' in request.META:
            return cors_preflight_response(request)
        _locals = get_locals()
        _locals.request = request
        rdict = {}
        akey = "access_token"

        # Add site name to request object
        request.SITE_NAME = settings.SITE_NAME
        request.footer = " (( {0} {1} ))".format(request.SITE_NAME.split("_")[0], "11.06")

        for key in request.GET.keys():
            if key.lower() == akey:
                akey = key
        if request.GET.has_key(akey):
            access_token = request.GET[akey]
        elif "HTTP_ACCESS_TOKEN" in request.META:
            access_token = request.META["HTTP_ACCESS_TOKEN"]
        else:
            access_token = None
        # if the request is made with a token check auth/magically authenticate
        if access_token is not None and Token.objects.filter(secret=access_token).exists():
            token = Token.objects.get(secret=access_token)
            valid = datetime.utcnow() - timedelta(seconds=token.timeout) < token.modified
            valid = valid or token.timeout == 0
            if valid:
                # set backend to first available and log user in
                token.user.backend = settings.AUTHENTICATION_BACKENDS[0]
                request.user = token.user
                # refresh tokens modified date
                token.modified = datetime.utcnow()
                token.save()
            else:
                token.delete()
                token = False
        else:
            token = False

        # Required user authentication for all views
        if hasattr(settings, 'ALLOW_ANONYMOUS_ACCESS') and not token: # Ignore authenticated tokens
            # No-brainer: check django.contrib.auth.middleware.AuthenticationMiddleware is installed
            assert hasattr(request, 'user')
            # Require user authentication by default, except for any exempt URLs.
            if not settings.ALLOW_ANONYMOUS_ACCESS and not request.user.is_authenticated():
                path = request.path_info.lstrip('/')
                if not any(m.match(path) for m in EXEMPT_URLS):
                    return http.HttpResponseRedirect(settings.LOGIN_URL)
        return None

    def process_response(self, request, response):
        return cors_preflight_response(request, response)

