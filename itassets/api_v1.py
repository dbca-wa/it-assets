from django.urls import path, include
from organisation.api_v1 import DepartmentUserResource, LocationResource


urlpatterns = [
    path('locations/', include(LocationResource.urls())),
    path('users/', include(DepartmentUserResource.urls())),
]
