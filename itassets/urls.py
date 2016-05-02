from django.conf import settings
from django.conf.urls import url, patterns, include
from django.views.generic import RedirectView
from django.contrib import admin
from assets import urls as assets_urls

admin.autodiscover()

urlpatterns = patterns(
    '',
    url(r'^$', RedirectView.as_view(url='/admin')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^assets/', include(assets_urls)),
)

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += patterns(
        '',
        url(r'^__debug__/', include(debug_toolbar.urls)),
    )
