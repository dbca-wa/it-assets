from django.conf.urls import *

# URL patterns for DEC example app
urlpatterns = patterns('dec_base.views', # You'll need to edit this line if you move the example app out of dec_base.
    url(r'^home/$', 'home', name='example_app_home'), # Named URLs are extremely useful!
    (r'^sidebar/$', 'sidebar'), # You don't need to use named URLs all the time, and multiple URLs can use the same view.
    url(r'^$', 'home', name='site_home'),
)

