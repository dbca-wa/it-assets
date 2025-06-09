from django.conf import settings
from django.contrib import admin
from django.urls import include, path, reverse_lazy
from django.views.generic import RedirectView

from itassets.api_v3 import urlpatterns as api_v3_urlpatterns
from organisation import urls as organisation_urls
from organisation.admin import service_desk_admin_site

urlpatterns = [
    path("admin/", admin.site.urls),
    path("service-desk-admin/", service_desk_admin_site.urls, name="service_desk_admin"),
    path("api/v3/", include(api_v3_urlpatterns)),
    path("organisation/", include(organisation_urls)),
    path("favicon.ico", RedirectView.as_view(url=f"{settings.STATIC_URL}favicon.ico"), name="favicon"),
    path("", RedirectView.as_view(url=reverse_lazy("service_desk_admin:index"))),
]
