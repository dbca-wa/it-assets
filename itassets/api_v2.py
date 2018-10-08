from django.conf.urls import include, url
from rest_framework import routers

from webconfig.api_v2 import SiteViewSet
from organisation.api_v2 import DepartmentUserViewSet, DepartmentTreeViewSet, LocationViewSet, OrgUnitViewSet, OrgTreeViewSet
from registers.api import  ChangeRequestViewSet, StandardChangeViewSet

api_v2_router = routers.DefaultRouter()
api_v2_router.register(r'webconfig', SiteViewSet)

api_v2_router.register(r'departmenttree', DepartmentTreeViewSet)
api_v2_router.register(r'departmentuser', DepartmentUserViewSet)
api_v2_router.register(r'location', LocationViewSet)
api_v2_router.register(r'orgunit', OrgUnitViewSet)
api_v2_router.register(r'orgtree', OrgTreeViewSet)
api_v2_router.register(r'changerequest',ChangeRequestViewSet)
api_v2_router.register(r'standardchange', StandardChangeViewSet)
