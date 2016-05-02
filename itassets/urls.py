import os

from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.conf.urls import url, patterns, include
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
#from django.views.generic.simple import redirect_to
from django.views.generic import RedirectView 

from django.db.models import get_models, get_app
from django.contrib import admin

import uni_form
import assets.urls

admin.autodiscover()

app_list = ["restless", "assets"]
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

# Tack the site name onto AuthenticationForm, for the purpose of displaying it on the login template.
AuthenticationForm.sitetitle = 'Assets'

urlpatterns = patterns('',
    #url(r'^$', redirect_to, {'url': '/admin'}),
    url(r'^$', RedirectView.as_view(url = '/admin')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^assets/', include(assets.urls)),
    url(r'^login/$', 'django.contrib.auth.views.login', name='login', kwargs={'template_name':'dec_base/login.html', 'authentication_form': AuthenticationForm}),
    url(r'^logout/$', 'django.contrib.auth.views.logout', name='logout', kwargs={'template_name':'dec_base/logged_out.html'}),
    #url(r'^confluence', 'django.views.generic.simple.redirect_to', {'url': 'https://confluence.dec.wa.gov.au/display/assets'}, name='help_page'),
    url(r'^$', RedirectView.as_view(url = 'https://confluence.dec.wa.gov.au/display/assets'), name='help_page'),
    url(r'^api/restless/v1/', include('restless.urls')),
    #url(r'^favicon\.ico$', 'django.views.generic.simple.redirect_to', {'url': '/static/img/favicon.ico'}),
    url(r'^favicon\.ico$', RedirectView.as_view(url='/static/img/favicon.ico')),
    url(r'^media/uni_form/(?P<path>.*)$',  'django.views.static.serve', {
        'document_root': os.path.join(os.path.dirname(os.path.realpath(uni_form.__file__)), 'media', 'uni_form')
    }),
)

urlpatterns += staticfiles_urlpatterns()
