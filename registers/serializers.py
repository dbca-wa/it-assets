from .models import ChangeRequest, StandardChange, ITSystem
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
    it_systems = ITSystemSerializer(many = True)

    #changing requestor to requester
    requester = DepartmentUserMinSerializer()

    endorser = DepartmentUserMinSerializer()

    # changing implementor to implementer
    implementer = DepartmentUserMinSerializer()

    class Meta:
        model = ChangeRequest
        fields = '__all__'


class StandardChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = StandardChange
        fields = '__all__'
