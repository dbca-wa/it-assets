from django.urls import path, include

from organisation.api import DepartmentUserResource, UserSelectResource
from organisation.views import DepartmentUserAPIResource, LocationAPIResource
from itassets.api_v1 import OptionResource


urlpatterns = [
    path('departmentuser/', DepartmentUserAPIResource.as_view(), name='department_user_api_resource'),
    path('location/', LocationAPIResource.as_view(), name='location_api_resource'),
    # TODO: Deprecate the endpoints below when possible.
    path('users/', include(DepartmentUserResource.urls())),
    path('user-select/', include(UserSelectResource.urls())),  # Used by the RFC form views.
    path('options/', include(OptionResource.urls())),
]
