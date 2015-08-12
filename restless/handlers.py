from piston.handler import BaseHandler, AnonymousBaseHandler
from piston.utils import rc, require_mime, require_extended
from django.contrib.auth.models import User, AnonymousUser

class OAuth(object):
    """
    
    Authentication handlers must implement two methods:
     - `is_authenticated`: Will be called when checking for
        authentication. Receives a `request` object, please
        set your `User` object on `request.user`, otherwise
        return False (or something that evaluates to False.)
     - `challenge`: In cases where `is_authenticated` returns
        False, the result of this method will be returned.
        This will usually be a `HttpResponse` object with
        some kind of challenge headers and 401 code on it.
    """
    def __init__(self, realm='API'):
        self.realm = realm

    def is_authenticated(self, request):
        try:
            auth_token = getattr(request, request.method)["auth_token"]
        except:
            return False

        if request.user not in (False, None, AnonymousUser()):
            cache.set("api_auth_token" + auth_token, request.user.pk, 600)

        userpk = cache.get("api_auth_token" + auth_token)

        if userpk:
            request.user = User.objects.get(pk=userpk)
            # need to login user with django session here
            cache.set("api_auth_token" + auth_token, request.user.pk, 600)
            return True
        else:
            return False

    def challenge(self):
        #omg write lator
        resp = HttpResponse("Authorization Required")
        resp['WWW-Authenticate'] = 'Basic realm="%s"' % self.realm
        resp.status_code = 401
        return resp

class TestHandler(BaseHandler):
    """
    Authenticated entrypoint for your amazing api
    """
    
    def read(self, request): # title=None):
        print "read ", attrs
        return {"omg":"what"}
