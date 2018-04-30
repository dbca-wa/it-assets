from django.urls import path, include
from django.views.generic import RedirectView
from django.contrib import admin
from itassets.api import api_urlpatterns
from itassets.views import HealthCheckView
from knowledge import urls as knowledge_urls

admin.site.site_header = 'IT Assets database administration'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(api_urlpatterns)),
    path('knowledge/', include(knowledge_urls)),
    path('healthcheck/', HealthCheckView.as_view(), name='health_check'),
    path('', RedirectView.as_view(url='/admin')),
]
