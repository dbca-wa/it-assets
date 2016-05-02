from django.conf import settings
from django.conf.urls import url, patterns, include
from django.views.generic import RedirectView
from django.contrib import admin
import assets.urls

admin.autodiscover()

urlpatterns = patterns(
    '',
    url(r'^$', RedirectView.as_view(url='/admin')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^assets/', include(assets.urls)),
    #url(r'^login/$', 'django.contrib.auth.views.login', name='login', kwargs={'template_name':'dec_base/login.html', 'authentication_form': AuthenticationForm}),
    #url(r'^logout/$', 'django.contrib.auth.views.logout', name='logout', kwargs={'template_name':'dec_base/logged_out.html'}),
)

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += patterns('',
        url(r'^__debug__/', include(debug_toolbar.urls)),
    )
