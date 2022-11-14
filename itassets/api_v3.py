from django.conf import settings
from django.urls import path
from django.views.decorators.cache import cache_page
from organisation.views import DepartmentUserAPIResource, LocationAPIResource, LicenseAPIResource
from registers.views import ITSystemAPIResource


urlpatterns = [
    path('departmentuser/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(DepartmentUserAPIResource.as_view()), name='department_user_api_resource'),
    path('departmentuser/<int:pk>/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(DepartmentUserAPIResource.as_view()), name='department_user_api_resource'),
    path('location/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(LocationAPIResource.as_view()), name='location_api_resource'),
    path('location/<int:pk>/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(LocationAPIResource.as_view()), name='location_api_resource'),
    path('license/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(LicenseAPIResource.as_view()), name='license_api_resource'),
    path('license/<int:pk>/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(LicenseAPIResource.as_view()), name='license_api_resource'),
    path('itsystem/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(ITSystemAPIResource.as_view()), name='it_system_api_resource'),
    path('itsystem/<int:pk>/', cache_page(settings.API_RESPONSE_CACHE_SECONDS)(ITSystemAPIResource.as_view()), name='it_system_api_resource'),
]
