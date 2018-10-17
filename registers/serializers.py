from .models import ChangeRequest, ChangeApproval, StandardChange, ITSystem
from organisation.api_v2 import DepartmentUserMinSerializer
from rest_framework import serializers


class ITSystemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ITSystem
        fields = (
            'pk',
            'name',
            'system_id'
        )


class ChangeRequestSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField()
    it_system = ITSystemSerializer()
    requestor = DepartmentUserMinSerializer()
    approver = DepartmentUserMinSerializer()
    implementor = DepartmentUserMinSerializer()

    class Meta:
        model = ChangeRequest
        fields = '__all__'


class ChangeApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChangeApproval
        fields = '__all__'


class StandardChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = StandardChange
        fields = '__all__'
