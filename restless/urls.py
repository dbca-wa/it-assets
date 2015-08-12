from django.conf import settings
from django.conf.urls import *

urlpatterns = patterns('restless.views',
    url(r'{0}/request_token'.format(settings.SITE_NAME), 'request_access_token'),
    url(r'{0}/list_tokens'.format(settings.SITE_NAME), 'list_access_tokens'),
    url(r'{0}/delete_token'.format(settings.SITE_NAME), 'delete_access_token'),
    url(r'{0}/list_roles'.format(settings.SITE_NAME), 'list_roles'),
    url(r'{0}/validate_token'.format(settings.SITE_NAME), 'validate_token'),
    url(r'validate_token', 'validate_token'),
    # automated documentation url(r'^$', documentation_view),
)
