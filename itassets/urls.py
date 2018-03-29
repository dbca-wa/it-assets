from django.conf.urls import url, include
from django.views.generic import RedirectView
from django.contrib import admin
from itassets.api import api_urlpatterns
from knowledge import urls as knowledge_urls

admin.site.site_header = 'IT Assets database administration'

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^api/', include(api_urlpatterns)),
    url(r'^knowledge/', include(knowledge_urls)),
    url(r'^$', RedirectView.as_view(url='/admin')),
]
