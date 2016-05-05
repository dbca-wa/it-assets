from django.conf import settings
from django.conf.urls import url, include
from django.views.generic import RedirectView
from assets.admin import admin_site


urlpatterns = [
    url(r'^$', RedirectView.as_view(url='/admin')),
    url(r'^admin/', admin_site.urls),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns.append(url(r'^__debug__/', include(debug_toolbar.urls)))
