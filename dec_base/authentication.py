import ldap, os
from django_auth_ldap.config import LDAPSearch, GroupOfNamesType

# Baseline configuration.
#AUTH_LDAP_SERVER_URI = "ldap://corporateict.domain:3268"
AUTH_LDAP_SERVER_URI = os.environ['LDAP_SERVER_URI']

#AUTH_LDAP_BIND_DN = "atlassian-admin@corporateict.domain"
AUTH_LDAP_BIND_DN = os.environ['LDAP_ACCESS_DN']

#AUTH_LDAP_BIND_PASSWORD = "p7_9Yyzzal"
AUTH_LDAP_BIND_PASSWORD = os.environ['LDAP_ACCESS_PASSWORD']

AUTH_LDAP_USER_SEARCH = LDAPSearch("DC=corporateict,DC=domain",
    ldap.SCOPE_SUBTREE, "(sAMAccountName=%(user)s)")

# Set up the basic group parameters.
AUTH_LDAP_GROUP_SEARCH = LDAPSearch("DC=corporateict,DC=domain",
    ldap.SCOPE_SUBTREE, "(objectClass=group)"
)

AUTH_LDAP_GLOBAL_OPTIONS = {
    ldap.OPT_X_TLS_REQUIRE_CERT: False,
    ldap.OPT_REFERRALS: False,
}

AUTH_LDAP_GROUP_TYPE = GroupOfNamesType(name_attr="cn")

# Only users in this group can log in.
#AUTH_LDAP_REQUIRE_GROUP = "cn=enabled,ou=django,ou=groups,dc=example,dc=com"

# Populate the Django user from the LDAP directory.
AUTH_LDAP_USER_ATTR_MAP = {
    "first_name": "givenName",
    "last_name": "sn",
    "email": "mail"
}

'''AUTH_LDAP_USER_FLAGS_BY_GROUP = {
    "is_staff": "DC=corporateict,DC=domain",
    "is_superuser": "CN=Atlassian Admins,OU=Crowd,OU=_Global,OU=Sites,DC=corporateict,DC=domain"
}'''

AUTH_LDAP_USER_FLAGS_BY_GROUP = {
    "is_staff": "CN=Atlassian Admins,OU=Crowd,OU=_Global,OU=Sites,DC=corporateict,DC=domain",
    "is_superuser": "CN=Atlassian Admins,OU=Crowd,OU=_Global,OU=Sites,DC=corporateict,DC=domain"
}

AUTH_LDAP_ALWAYS_UPDATE_USER = False
AUTH_LDAP_AUTHORIZE_ALL_USERS = True

# Use LDAP group membership to calculate group permissions.
AUTH_LDAP_FIND_GROUP_PERMS = True
AUTH_LDAP_MIRROR_GROUPS = True

# Cache group memberships for an hour to minimize LDAP traffic
AUTH_LDAP_CACHE_GROUPS = False
# AUTH_LDAP_GROUP_CACHE_TIMEOUT = 300

# Keep ModelBackend around for per-user permissions and maybe a local superuser.
AUTHENTICATION_BACKENDS = (
    'django_auth_ldap.backend.LDAPBackend',
    'django.contrib.auth.backends.ModelBackend',
)

import logging 

logger = logging.getLogger('django_auth_ldap')
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)
