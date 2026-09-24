from django.urls import path

from organisation.views import CostCentreAPIResource, DepartmentUserAPIResource, LicenseAPIResource, LocationAPIResource
from itsystems.views import ITSystemRecordAPIResource

urlpatterns = [
    path("departmentuser/", DepartmentUserAPIResource.as_view(), name="department_user_api_resource"),
    path("departmentuser/<int:pk>/", DepartmentUserAPIResource.as_view(), name="department_user_api_resource"),
    path("location/", LocationAPIResource.as_view(), name="location_api_resource"),
    path("location/<int:pk>/", LocationAPIResource.as_view(), name="location_api_resource"),
    path("license/", LicenseAPIResource.as_view(), name="license_api_resource"),
    path("license/<int:pk>/", LicenseAPIResource.as_view(), name="license_api_resource"),
    path("itsystem/", ITSystemRecordAPIResource.as_view(), name="it_system_api_resource"),
    path("itsystem/<str:system_id>/", ITSystemRecordAPIResource.as_view(), name="it_system_api_resource"),
    path("costcentre/", CostCentreAPIResource.as_view(), name="cost_centre_api_resource"),
    path("costcentre/<int:pk>/", CostCentreAPIResource.as_view(), name="cost_centre_api_resource"),
]
