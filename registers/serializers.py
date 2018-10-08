from .models import ChangeRequest, ChangeApproval, StandardChange, ITSystem
from organisation.api_v2 import DepartmentUserMinSerializer
from rest_framework import serializers

class ITSystemSerializer(serializers.ModelSerializer):
    class Meta:
        fields = (
            'pk',
            'name',
            'system_id'
            )
        model = ITSystem

class ChangeRequestSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField()
    it_system = ITSystemSerializer()
    requestor = DepartmentUserMinSerializer()
    approver = DepartmentUserMinSerializer()
    implementor = DepartmentUserMinSerializer()
    class Meta:
        fields = (
            'id',
            'requestor',
            'approver',
            'implementor',
            'title',
            'description',
            'change_type',
            'urgency',
            'submission_date',
            'completed_date',
            'change_start',
            'change_end',
            'alternate_system',
            'outage',
            'implementation',
            'implementation_docs',
            'broadcast',
            'notes',
            'status',
            'unexpected_issues',
            'caused_issues',
            'it_system',
            'editable'
        )
        model = ChangeRequest

class ChangeApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        fields = '__all__'
        model = ChangeApproval

class StandardChangeSerializer(serializers.ModelSerializer):
    class Meta:
        fields = '__all__'
        model = StandardChange