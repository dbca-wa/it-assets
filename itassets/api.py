from django.urls import path, include

from organisation.api_v1 import DepartmentUserResource, UserSelectResource
from itassets.api_v1 import OptionResource


urlpatterns = [
    # TODO: Deprecate the endpoints below when possible.
    path('users/', include(DepartmentUserResource.urls())),
    path('user-select/', include(UserSelectResource.urls())),  # Used by the RFC form views.
    path('options/', include(OptionResource.urls())),
]
