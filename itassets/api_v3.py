from django.urls import path
from organisation.views import DepartmentUserAPIResource, LocationAPIResource, OrgUnitAPIResource, LicenseAPIResource


urlpatterns = [
    path('departmentuser/', DepartmentUserAPIResource.as_view(), name='department_user_api_resource'),
    path('location/', LocationAPIResource.as_view(), name='location_api_resource'),
    path('orgunit/', OrgUnitAPIResource.as_view(), name='orgunit_api_resource'),
    path('license/', LicenseAPIResource.as_view(), name='license_api_resource'),
]
