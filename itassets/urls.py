from django.conf import settings
from django.urls import path, include
from django.views.generic import RedirectView
from django.contrib import admin
from itassets.api import api_urlpatterns
from itassets.api_v2 import api_v2_router
from itassets.views import HealthCheckView
from knowledge import urls as knowledge_urls
from rancher import urls as rancher_urls
from registers import urls as registers_urls
from assets import urls as assets_urls
from organisation import urls as organisation_urls


admin.site.site_header = 'IT Assets database administration'
admin.site.index_title = 'IT Assets database'
admin.site.site_title = 'IT Assets'


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v2/', include(api_v2_router.urls)),
    path('api/v1/', include(api_urlpatterns)),
    path('api/', include(api_urlpatterns)),
    path('assets/', include(assets_urls)),
    path('knowledge/', include(knowledge_urls)),
    path('rancher/', include(rancher_urls)),
    path('registers/', include(registers_urls)),
    path('organisation/', include(organisation_urls)),
    path('healthcheck/', HealthCheckView.as_view(), name='health_check'),
    path('favicon.ico', RedirectView.as_view(url='{}favicon.ico'.format(settings.STATIC_URL)), name='favicon'),
    path('', RedirectView.as_view(url='/admin')),
]

urlpatterns += [
    path('api-auth/', include('rest_framework.urls')),
]
