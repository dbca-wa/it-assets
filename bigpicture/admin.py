from django.contrib import admin
from reversion.admin import VersionAdmin
from .models import Dependency, Platform, RiskAssessment


class ModelDescMixin(object):
    """A small mixin for the ModelAdmin class to add a description of the model to the
    admin changelist view context.

    In order to then display this description above the list view, you then need to
    override the relevant change_list.html template.
    """

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        if hasattr(self, "model_description"):
            extra_context["model_description"] = self.model_description
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(Dependency)
class DependencyAdmin(ModelDescMixin, VersionAdmin):
    fields = ("content_type", "object_id", "category", "health")
    list_display = ("content_object", "category", "health", "updated")
    list_filter = ("category", "health")
    model_description = Dependency.__doc__


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
