from django.conf.urls import url, patterns
from views import export, import_asset, do_import, categories

urlpatterns = patterns('',
    url(r'^export/', export),
    url(r'^import/final$', do_import),
    url(r'^import/$', import_asset),
    url(r'^categories/$', categories),
)
