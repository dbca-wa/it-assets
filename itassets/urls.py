from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from itassets.api_v3 import urlpatterns as api_v3_urlpatterns
from organisation import urls as organisation_urls
from organisation.models import AscenderActionLog, CostCentre, DepartmentUser, Location

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v3/", include(api_v3_urlpatterns)),
    path("organisation/", include(organisation_urls)),
    path("favicon.ico", RedirectView.as_view(url=f"{settings.STATIC_URL}favicon.ico"), name="favicon"),
]


class ServiceDeskAdminSite(admin.AdminSite):
    """Define a customised admin site for Service Desk staff."""

    site_header = "IT Assets database administration"
    index_title = "IT Assets database"
    site_title = "IT Assets"
    site_url = None


service_desk_admin_site = ServiceDeskAdminSite(name="service_desk_admin")
service_desk_admin_site.register([AscenderActionLog, CostCentre, DepartmentUser, Location])

urlpatterns += [
    path("service-desk-admin/", service_desk_admin_site.urls),
    path("", RedirectView.as_view(url="service-desk-admin/")),
]
