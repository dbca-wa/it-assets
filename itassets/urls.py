from django.conf.urls import url, include
from django.views.generic import RedirectView
from django.contrib import admin
from itassets.api import api_urlpatterns

admin.site.site_header = 'IT Assets database administration'

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^api/', include(api_urlpatterns)),
    url(r'^$', RedirectView.as_view(url='/admin')),
]
