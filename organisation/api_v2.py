
from rest_framework import viewsets, serializers, status, generics, views
from rest_framework.decorators import detail_route, list_route, renderer_classes, authentication_classes, permission_classes
from rest_framework_recursive.fields import RecursiveField

from organisation.models import Location, OrgUnit, DepartmentUser


class UserLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ('id', 'name')


class UserOrgUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgUnit
        fields = ('id', 'name', 'acronym')


class DepartmentUserSerializer(serializers.ModelSerializer):
    location = UserLocationSerializer()
    org_unit = UserOrgUnitSerializer()
    group_unit = UserOrgUnitSerializer()
    #children = serializers.ListField(source='children_filtered')

    class Meta:
        model = DepartmentUser
        fields = (
            'id', 'name', 'preferred_name', 'email', 'username', 'title', 'employee_id',
            'telephone', 'extension', 'mobile_phone',
            'location',
            'photo_ad',
            'org_unit',
            'group_unit',
            'org_unit_chain',
            'parent',
            'children',
        )


class DepartmentUserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DepartmentUser.objects.filter(
        **DepartmentUser.ACTIVE_FILTER
    ).exclude(
        account_type__in=DepartmentUser.ACCOUNT_TYPE_EXCLUDE
    ).prefetch_related(
        'location', 'children',
        'org_unit', 'org_unit__children',
    ).order_by('name')
    serializer_class = DepartmentUserSerializer


class DepartmentTreeSerializer(serializers.ModelSerializer):
    children = serializers.ListField(source='children_filtered', child=RecursiveField())
    class Meta:
        model = DepartmentUser
        fields = ('id', 'name', 'title', 'children')


class DepartmentTreeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DepartmentUser.objects.filter(**DepartmentUser.ACTIVE_FILTER).exclude(account_type__in=DepartmentUser.ACCOUNT_TYPE_EXCLUDE).filter(parent__isnull=True)
    serializer_class = DepartmentTreeSerializer


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ('id', 'name', 'point', 'manager', 'address', 'pobox', 'phone', 'fax', 'email', 'url', 'bandwidth_url')


class LocationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Location.objects.filter(active=True)
    serializer_class = LocationSerializer


class OrgUnitSerializer(serializers.ModelSerializer):
    unit_type = serializers.CharField(source='get_unit_type_display')

    class Meta:
        model = OrgUnit
        fields = ('id', 'name', 'acronym', 'unit_type', 'manager', 'parent', 'children', 'location')


class OrgUnitViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OrgUnit.objects.filter(active=True)
    serializer_class = OrgUnitSerializer


class OrgTreeSerializer(serializers.ModelSerializer):
    children = serializers.ListField(source='children.all', child=RecursiveField())
    class Meta:
        model = OrgUnit
        fields = ('id', 'name', 'children')


class OrgTreeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OrgUnit.objects.filter(active=True, parent__isnull=True)
    serializer_class = OrgTreeSerializer
