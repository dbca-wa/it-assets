from django.conf.urls import include, url
from rest_framework import routers

from webconfig.api_v2 import SiteViewSet
from organisation.api_v2 import LocationViewSet, OrgUnitViewSet, OrgTreeViewSet

api_v2_router = routers.DefaultRouter()
api_v2_router.register(r'webconfig', SiteViewSet)
api_v2_router.register(r'location', LocationViewSet)
api_v2_router.register(r'orgunit', OrgUnitViewSet)
api_v2_router.register(r'orgtree', OrgTreeViewSet)
