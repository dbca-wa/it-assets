
from rest_framework import viewsets, serializers, status, generics, views
from rest_framework.decorators import detail_route, list_route, renderer_classes, authentication_classes, permission_classes

from webconfig.models import Site, Location, FQDN, Domain


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ('path', 'rules', 'auth_level', 'allow_cors', 'allow_websockets')


class SiteSerializer(serializers.ModelSerializer):
    locations = LocationSerializer(many=True, read_only=True)
    fqdn = serializers.StringRelatedField()
    aliases = serializers.StringRelatedField(many=True)

    class Meta:
        model = Site
        fields = ('fqdn', 'enabled', 'status', 'availability', 'aliases', 'allow_https', 'allow_http', 'rules', 'locations')


class SiteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Site.objects.order_by('fqdn__name', 'fqdn__domain__name')
    serializer_class = SiteSerializer
