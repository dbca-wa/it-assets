from django.conf import settings
from django.contrib import admin
from django.contrib.sites.models import Site
from django.urls import include, path
from django.views.generic import RedirectView

from itassets.api_v3 import urlpatterns as api_v3_urlpatterns
from organisation import urls as organisation_urls

admin.site.site_header = "IT Assets database administration"
admin.site.index_title = "IT Assets database"
admin.site.site_title = "IT Assets"
admin.site.unregister(Site)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v3/", include(api_v3_urlpatterns)),
    path("organisation/", include(organisation_urls)),
    path("favicon.ico", RedirectView.as_view(url=f"{settings.STATIC_URL}favicon.ico"), name="favicon"),
    path("", RedirectView.as_view(url="/admin")),
]
