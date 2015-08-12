from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template

# URL patterns for DEC example app
urlpatterns = patterns('example_app.views',
    url(r'^example-app/home/$', 'index_page', name='example_app_home'), # Named URLs are extremely useful!
    (r'^example-app/$', 'index_page'), # You don't need to use named URLs all the time, and multiple URLs can use the same view
)
