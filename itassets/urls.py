from django.conf import settings
from django.urls import path, include
from django.views.generic import RedirectView
from django.contrib import admin
from itassets.api import api_urlpatterns
from itassets.api_v2 import api_v2_router
from itassets.views import HealthCheckView
from knowledge import urls as knowledge_urls
from recoup import urls as recoup_urls
from registers import urls as registers_urls

#Temp added for hardware assets api
from django.conf.urls import include

admin.site.site_header = 'IT Assets database administration'
admin.site.index_title = 'IT Assets database'
admin.site.site_title = 'IT Assets'



urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v2/', include(api_v2_router.urls)),
    path('api/', include(api_urlpatterns)),
    path('knowledge/', include(knowledge_urls)),
    path('recoup/', include(recoup_urls)),
    path('registers/', include(registers_urls)),
    path('healthcheck/', HealthCheckView.as_view(), name='health_check'),
    path('', RedirectView.as_view(url='/admin')),
    path('favicon.ico', RedirectView.as_view(url='{}favicon.ico'.format(settings.STATIC_URL)), name='favicon'),
]

urlpatterns += [
    path('api-auth/', include('rest_framework.urls')),
]