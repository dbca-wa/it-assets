from django.contrib import admin
from reversion.admin import VersionAdmin

from itassets.utils import ModelDescMixin
from .models import Dependency, Platform, RiskAssessment


@admin.register(Dependency)
class DependencyAdmin(ModelDescMixin, VersionAdmin):
    fields = ("content_type", "object_id", "category")
    list_display = ("content_object", "category", "updated")
    list_filter = ("category",)
    model_description = Dependency.__doc__
    search_fields = ("name",)


@admin.register(Platform)
class PlatformAdmin(ModelDescMixin, VersionAdmin):
    fields = ("name", "dependencies", "tier", "health")
    list_display = ("name", "tier", "health", "updated")
    list_filter = ("tier", "health")
    model_description = Platform.__doc__
    search_fields = ("name",)


@admin.register(RiskAssessment)
class RiskAssessmentAdmin(ModelDescMixin, VersionAdmin):
    fields = ("content_type", "object_id", "category", "rating", "notes")
    list_display = ("content_object", "category", "rating", "updated")
    list_filter = ("category", "rating")
    model_description = RiskAssessment.__doc__
    search_fields = ("notes",)
