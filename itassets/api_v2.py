from django.conf.urls import include, url
from rest_framework import routers

from webconfig.api_v2 import SiteViewSet

api_v2_router = routers.DefaultRouter()
api_v2_router.register(r'webconfig', SiteViewSet)

