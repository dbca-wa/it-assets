from django.conf import settings
from django.urls import path, include
from django.views.generic import RedirectView
from django.contrib import admin
from itassets.api_v3 import urlpatterns as api_v3_urlpatterns
from rancher import urls as rancher_urls
from registers import urls as registers_urls
from organisation import urls as organisation_urls


admin.site.site_header = 'IT Assets database administration'
admin.site.index_title = 'IT Assets database'
admin.site.site_title = 'IT Assets'


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v3/', include(api_v3_urlpatterns)),
    path('rancher/', include(rancher_urls)),
    path('registers/', include(registers_urls)),
    path('organisation/', include(organisation_urls)),
    path('markdownx/', include('markdownx.urls')),
    path('favicon.ico', RedirectView.as_view(url='{}favicon.ico'.format(settings.STATIC_URL)), name='favicon'),
    path('', RedirectView.as_view(url='/admin')),
]
