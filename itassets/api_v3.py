from django.urls import path
from organisation.views import DepartmentUserAPIResource, LocationAPIResource, OrgUnitAPIResource


urlpatterns = [
    path('departmentuser/', DepartmentUserAPIResource.as_view(), name='department_user_api_resource'),
    path('location/', LocationAPIResource.as_view(), name='location_api_resource'),
    path('orgunit/', OrgUnitAPIResource.as_view(), name='orgunit_api_resource'),
]
