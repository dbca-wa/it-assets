from django.urls import path, include
from organisation.api_v1 import DepartmentUserResource


urlpatterns = [
    # FIXME: Deprecate the endpoint below when possible.
    path('users/', include(DepartmentUserResource.urls())),
]
