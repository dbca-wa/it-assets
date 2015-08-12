'''
Views for restless to manipulate applinks::

    Copyright (C) 2011 Department of Environment & Conservation           

    Authors:
     * Adon Metcalfe
                                                                            
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
import os, hashlib, base64, shutil

from datetime import datetime
from tempfile import mkdtemp

from django import http
from django.conf import settings
#from django.utils import simplejson as json
import simplejson as json
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache

from django_auth_ldap.backend import LDAPBackend

from restless.models import User, ApplicationLink, Token, get_roles, get_permissions, has_permission

ldapbackend = LDAPBackend()

def crossdomain(view):
    def wrapped(request, *args, **kw):
        if request.method == "OPTIONS":
            response = http.HttpResponse()
        else:
            response = view(request, *args, **kw)
        if request.META.has_key("HTTP_ORIGIN"):
            response["Access-Control-Allow-Origin"] = request.META["HTTP_ORIGIN"]
            response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response["Access-Control-Allow-Headers"] = "Content-Type, X-Requested-With"
            response["Access-Control-Allow-Credentials"] = "true"
        return response
    return wrapped

def intmpdir(func):
    def wrapped(*args, **kw):
        cwd = os.getcwd()
        workdir = mkdtemp()
        os.chdir(workdir)
        try:
            response = func(*args, **kw)
        except:
            os.chdir(cwd)
            shutil.rmtree(workdir)
            raise
        else:
            os.chdir(cwd)
            shutil.rmtree(workdir)
        return response
    return wrapped

def list_roles(request, fmt="json"):
    groups = [group.name for group in request.user.groups.all()]
    return http.HttpResponse(json.dumps({
        "username": request.user.username,
        "groups": groups,
        "roles": [str(r) for r in get_roles(request.user)],
        "content_permissions": [str(p) for p in get_permissions(request.user)]
    }))

@crossdomain
def validate_token(request):
    # Middleware should refresh token if required
    # just return true/false on whether user is logged in
    if request.user.is_authenticated():
        return http.HttpResponse("true")
    else:
        return http.HttpResponse("false")

def validate_request(requestdata):
    '''
    validates a dictionary of requestdata
    and returns a restless User, ApplicationLink and token expiry time
    '''
    # sanity check the dictionary
    for key in ["client_id", "client_secret", "user_id" ]:
        if not requestdata.has_key(key):
            raise Exception("Missing Input")

    # set default expiry to 10mins unless specified
    # 0 means never expires
    expires = 600
    if requestdata.has_key("expires"):
        expires= int(requestdata["expires"])

    # Try and find the user for the user_id
    user = requestdata["user_id"]
    if User.objects.filter(username = user):
        user = User.objects.get(username = user)
    else:
        try:
            ldapbackend.populate_user(user)
            user = User.objects.get(username = user)
        except:
            raise Exception("Invalid user_id")
     # Try and find the client_id
    if ApplicationLink.objects.filter(client_name = requestdata["client_id"], server_name = settings.SERVICE_NAME).exists():
        applink = ApplicationLink.objects.get(client_name = requestdata["client_id"], server_name = settings.SERVICE_NAME)
    # Validate the secret
    if applink.auth_method == ApplicationLink.AUTH_METHOD.basic:
        client_secret = applink.secret
    elif requestdata.has_key("nonce"):
        if cache.get(applink.secret) == requestdata["nonce"]:
            raise Exception("No you can't reuse nonce's!")
        cache.set(applink.secret, requestdata["nonce"], 3600)
        # client_secret should be hexdigest, hash algorithm selected based on applink
        client_secret = applink.get_client_secret(requestdata["user_id"], requestdata["nonce"])
    else:
        raise Exception("Missing nonce")
    if not client_secret == requestdata["client_secret"]:
        raise Exception("Invalid client_secret")
    return user, applink, expires

@csrf_exempt
def request_access_token(request):
    '''
    Create tokens on a well formed request
    '''
    if request.method == "POST":
        requestdata = request.POST
    else:
        requestdata = request.GET

    # Validate the request, get user and applink
    try:
        user, applink, expires = validate_request(requestdata = requestdata)
    except Exception, e:
        return http.HttpResponseForbidden(repr(e))
    else:
        # Get existing or generate a token for the user
        try:
            token = Token.objects.filter(timeout = expires, user = user, link = applink).order_by("modified")[0]
            token.modified = datetime.utcnow()
        except IndexError:
            token = Token(secret = base64.urlsafe_b64encode(os.urandom(8)),
                timeout = expires, user = user, link = applink)
        if requestdata.has_key("url"):
            token.url = requestdata["url"]
        token.save()
        return http.HttpResponse(token.secret)

    # Shouldn't be able to get here
    return http.HttpResponseForbidden("No token for you!")

@csrf_exempt
def delete_access_token(request):
    '''
    Delete access_token in a request
    '''
    if request.method == "POST":
        requestdata = request.POST
    else:
        requestdata = request.GET

    if requestdata.has_key("access_token"):
        try:
            token = Token.objects.get(secret = requestdata["access_token"])
        except Exception, e:
            return http.HttpResponseForbidden(repr(e))
        else:
            token.delete()
            return http.HttpResponse("Token {0} deleted".format(requestdata["access_token"]))
    else:
        return http.HttpResponseForbidden("Missing access_token")

@csrf_exempt
def list_access_tokens(request):
    '''
    List tokens for an available user (exact same post as requesting)
    '''
    if request.method == "POST":
        requestdata = request.POST
    else:
        requestdata = request.GET

    # Validate the request, get user and applink
    try:
        user, applink, expires = validate_request(requestdata = requestdata)
    except Exception, e:
        return http.HttpResponseForbidden(repr(e))
    else:
        # TODO: return different formats nicely
        return http.HttpResponse(repr([secret[0] for secret in applink.token_set.filter(user = user).values_list("secret")]))

def session(request):
    for key in request.GET.keys():
        request.session[key] = request.GET[key]
    if request.method == "POST":
        for key in request.POST.keys():
            request.session[key] = request.POST[key]
    return http.HttpResponse(json.dumps(request.session._session_cache, indent=2))
	

