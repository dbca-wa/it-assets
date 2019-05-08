from .models import HardwareAsset

from rest_framework import serializers


class HardwareAssetSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField()
    hardware_model = serializers.SerializerMethodField(read_only=True)
    vendor = serializers.SerializerMethodField(read_only=True)
    location = serializers.SerializerMethodField(read_only=True)
    assigned_user = serializers.SerializerMethodField(read_only=True)
    cost_centre = serializers.SerializerMethodField(read_only=True)


    class Meta:
        model = HardwareAsset
        fields = ('url', 'id',
                  'asset_tag', 'finance_asset_tag',
                  'serial', 'vendor',
                  'hardware_model', 'status',
                  'notes', 'cost_centre',
                  'location', 'assigned_user',
                  'date_purchased', 'purchased_value',
                  'is_asset', 'local_property',
                  'warranty_end',)

    def get_hardware_model(self, obj):
        return obj.hardware_model.model_type

    def get_vendor(self, obj):
        return obj.vendor.name

    def get_location(self, obj):
        if obj.location:
            return obj.location.name
        return None

    def get_assigned_user(self, obj):
        if obj.assigned_user:
            return obj.assigned_user.email
        return None

    def get_cost_centre(self, obj):
        if obj.cost_centre:
            return obj.cost_centre.name
        return None
