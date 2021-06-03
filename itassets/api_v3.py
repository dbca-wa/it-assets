from django.urls import path
from organisation.views import DepartmentUserAPIResource, LocationAPIResource, OrgUnitAPIResource, LicenseAPIResource
from registers.views import ITSystemAPIResource


urlpatterns = [
    path('departmentuser/', DepartmentUserAPIResource.as_view(), name='department_user_api_resource'),
    path('departmentuser/<int:pk>/', DepartmentUserAPIResource.as_view(), name='department_user_api_resource'),
    path('location/', LocationAPIResource.as_view(), name='location_api_resource'),
    path('location/<int:pk>/', LocationAPIResource.as_view(), name='location_api_resource'),
    path('orgunit/', OrgUnitAPIResource.as_view(), name='orgunit_api_resource'),
    path('orgunit/<int:pk>/', OrgUnitAPIResource.as_view(), name='orgunit_api_resource'),
    path('license/', LicenseAPIResource.as_view(), name='license_api_resource'),
    path('license/<int:pk>/', LicenseAPIResource.as_view(), name='license_api_resource'),
    path('itsystem/', ITSystemAPIResource.as_view(), name='it_system_api_resource'),
    path('itsystem/<int:pk>/', ITSystemAPIResource.as_view(), name='it_system_api_resource'),
]
