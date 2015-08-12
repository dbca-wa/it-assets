from django.contrib.auth.models import User

class EmailAuth(object):
    def authenticate(self, username=None, password=None):
        #email authentication
        try:
            user = User.objects.get(email__iexact=username)
            if user.check_password(password):
                return user
            else:
                try:
                    from django_auth_ldap.backend import LDAPBackend
                    ldapauth = LDAPBackend()
                    return ldapauth.authenticate(username=user.username, password=password)
                except:
                    return None
        except User.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
