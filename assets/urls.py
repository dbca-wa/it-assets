from django.conf.urls import url
from views import export, import_asset, do_import, categories

urlpatterns = [
    url(r'^export/', export),
    url(r'^import/final$', do_import),
    url(r'^import/$', import_asset, name='assets_import'),
    url(r'^categories/$', categories),
]
