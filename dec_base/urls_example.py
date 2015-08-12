import os

from django.conf.urls.defaults import url, patterns, include
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

from django.db.models import get_models, get_app
from django.contrib import admin

import uni_form

admin.autodiscover()

app_list = ["restless"]
for app_name in app_list:
    app_models = get_app(app_name)
    for model in get_models(app_models):
        try:
            try: # try and get enhanced admin
                admin.site.register(model, model.admin_config)
            except AttributeError:
                admin.site.register(model)
        except admin.sites.AlreadyRegistered:
            pass

urlpatterns = patterns('',
    #url(r'^sentry/', include('sentry.web.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^login/$', 'django.contrib.auth.views.login', name='login', kwargs={'template_name':'dec_base/login.html'}),
    url(r'^logout/$', 'django.contrib.auth.views.logout', name='logout', kwargs={'template_name':'dec_base/logged_out.html'}),
    url(r'^confluence', 'django.views.generic.simple.redirect_to', {'url': 'https://confluence.dec.wa.gov.au/display/PBS'}, name='help_page'),
    url(r'^api/restless/v1/', include('restless.urls')),
    url(r'^favicon\.ico$', 'django.views.generic.simple.redirect_to', {'url': '/static/img/favicon.ico'}),
    url(r'^media/uni_form/(?P<path>.*)$',  'django.views.static.serve', {
        'document_root': os.path.join(os.path.dirname(os.path.realpath(uni_form.__file__)), 'media', 'uni_form')
    }),
)

urlpatterns += staticfiles_urlpatterns()

urlpatterns += patterns('',
    url(r'^$', 'example_app.views.index_page', name='site_home'), # Make sure that you have a named URL called site_home, or the base templates will raise an exception.
)
