from rest_framework import viewsets
from assets.models import HardwareAsset
from assets.serializers import HardwareAssetSerializer
from rest_framework import permissions
from assets.permissions import IsAdminUserorReadOnly


class HardwareAssetViewSet(viewsets.ModelViewSet):
    queryset = HardwareAsset.objects.all()
    serializer_class = HardwareAssetSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAdminUserorReadOnly)
    http_method_names = ['get', 'Post', 'Put', 'head']
