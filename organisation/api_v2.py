from rest_framework import viewsets, serializers
from rest_framework_recursive.fields import RecursiveField

from organisation.models import Location, OrgUnit, DepartmentUser, CostCentre


class UserLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ('id', 'name')


class UserOrgUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgUnit
        fields = ('id', 'name', 'acronym')


class DepartmentUserMinSerializer(serializers.ModelSerializer):
    class Meta:
        model = DepartmentUser
        fields = ('id', 'name')


class DepartmentUserSerializer(serializers.ModelSerializer):
    location = UserLocationSerializer()
    org_unit = UserOrgUnitSerializer()
    group_unit = UserOrgUnitSerializer()

    class Meta:
        model = DepartmentUser
        fields = (
            'id', 'name', 'preferred_name', 'email', 'username', 'title',
            'telephone', 'extension', 'mobile_phone',
            'location', 'org_unit', 'group_unit',
        )


class DepartmentUserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DepartmentUser.objects.filter(
        **DepartmentUser.ACTIVE_FILTER
    ).exclude(
        account_type__in=DepartmentUser.ACCOUNT_TYPE_EXCLUDE
    ).prefetch_related(
        'location',
        'org_unit',
    ).order_by('name')
    serializer_class = DepartmentUserSerializer


class DepartmentTreeSerializer(serializers.ModelSerializer):

    class Meta:
        model = DepartmentUser
        fields = ('id', 'name', 'title')


class DepartmentTreeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DepartmentUser.objects.filter(**DepartmentUser.ACTIVE_FILTER).exclude(account_type__in=DepartmentUser.ACCOUNT_TYPE_EXCLUDE)
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
    children = serializers.ListField(source='children_active', child=RecursiveField())

    class Meta:
        model = OrgUnit
        fields = ('id', 'name', 'acronym', 'children')


class OrgTreeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OrgUnit.objects.filter(active=True, parent__isnull=True)
    serializer_class = OrgTreeSerializer


class CostCentreSerializer(serializers.ModelSerializer):
    class Meta:
        model = CostCentre
        fields = ('name', 'code', 'chart_acct_name', 'manager', 'business_manager', 'admin', 'tech_contact')


class CostCentreViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CostCentre.objects.filter(active=True)
    serializer_class = CostCentreSerializer
