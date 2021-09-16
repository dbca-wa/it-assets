from django.conf import settings
from django.urls import path, include
from django.views.generic import RedirectView
from django.contrib import admin
from itassets.api_v1 import urlpatterns as api_v1_urlpatterns
from itassets.api_v3 import urlpatterns as api_v3_urlpatterns
from itassets.api import urlpatterns as api_urlpatterns
from itassets.views import HealthCheckView
from rancher import urls as rancher_urls
from registers import urls as registers_urls
from assets import urls as assets_urls
from organisation import urls as organisation_urls


admin.site.site_header = 'IT Assets database administration'
admin.site.index_title = 'IT Assets database'
admin.site.site_title = 'IT Assets'


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v3/', include(api_v3_urlpatterns)),
    path('api/v1/', include(api_v1_urlpatterns)),
    path('api/', include(api_urlpatterns)),
    path('assets/', include(assets_urls)),
    path('rancher/', include(rancher_urls)),
    path('registers/', include(registers_urls)),
    path('organisation/', include(organisation_urls)),
    path('healthcheck/', HealthCheckView.as_view(), name='health_check'),
    path('markdownx/', include('markdownx.urls')),
    path('favicon.ico', RedirectView.as_view(url='{}favicon.ico'.format(settings.STATIC_URL)), name='favicon'),
    path('', RedirectView.as_view(url='/admin')),
]
