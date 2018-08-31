from django.contrib import admin
from django.db.models import Sum
from reversion.admin import VersionAdmin

from recoup import models


class InlineBillAdmin(admin.TabularInline):
    model = models.Bill
    fields = ["name", "year", "renewal_date", "cost", "cost_estimate"]
    extra = 0


@admin.register(models.Contract)
class ContractAdmin(VersionAdmin):
    list_display = ["__str__", "cost", "cost_estimate", "start", "active"]
    search_fields = ["bill__name", "bill__description", "bill__comment", "vendor", "reference", "brand"]
    inlines = [InlineBillAdmin]


class EndUserCostAdmin(admin.TabularInline):
    model = models.EndUserCost
    extra = 0
    ordering = ("-percentage",)


class ITPlatformCostAdmin(admin.TabularInline):
    model = models.ITPlatformCost
    extra = 0
    ordering = ("-percentage",)


class AllocatedListFilter(admin.SimpleListFilter):
    title = "Allocation"
    parameter_name = "allocated"

    def lookups(self, request, model_admin):
        return (
            ('0', 'None'),
            ('lt_100', 'Partially'),
            ('100', '100%'),
            ('gt_100', 'Over allocated')
        )

    def queryset(self, request, queryset):
        qs = queryset.annotate(Sum("cost_items__percentage"))
        if self.value() == "0":
            return qs.exclude(cost_items__percentage__gt=0)
        elif self.value() == "lt_100":
            return qs.filter(cost_items__percentage__sum__lt=100, cost_items__percentage__sum__gt=0)
        elif self.value() == "100":
            return qs.filter(cost_items__percentage__sum=100)
        elif self.value() == "gt_100":
            return qs.filter(cost_items__percentage__sum__gt=100)


@admin.register(models.Bill)
class BillAdmin(VersionAdmin):
    list_display = ["__str__", "contract", "quantity", "cost", "cost_estimate", "allocated", "active"]
    list_filter = ["year", AllocatedListFilter, "active"]
    search_fields = ["name", "description", "comment", "contract__vendor", "contract__reference", "contract__brand"]
    inlines = [EndUserCostAdmin, ITPlatformCostAdmin]


@admin.register(models.EndUserService)
class EndUserServiceAdmin(VersionAdmin):
    list_display = ["__str__", "total_user_count", "cost", "cost_estimate", "cost_percentage", "cost_estimate_percentage"]
    inlines = [EndUserCostAdmin]


class SystemDependencyAdmin(admin.TabularInline):
    model = models.SystemDependency
    extra = 0
    fields = ["platform", "weighting"]


@admin.register(models.ITPlatform)
class ITPlatformAdmin(VersionAdmin):
    list_display = ["__str__", "system_count", "system_weight_total", "cost", "cost_estimate", "cost_percentage", "cost_estimate_percentage"]
    inlines = [ITPlatformCostAdmin, SystemDependencyAdmin]


@admin.register(models.Division)
class DivisionAdmin(VersionAdmin):
    list_display = [
        "__str__", "user_count", "cc_count", "system_count", "bill", "cost", "cost_estimate",
        "cost_percentage", "cost_estimate_percentage", 'position']


@admin.register(models.CostCentreLink)
class CostCentreLinkAdmin(VersionAdmin):
    list_display = ["__str__", "cc", "division", "user_count", "system_count", "system_cost", "system_cost_estimate"]
    list_editable = ["user_count"]


@admin.register(models.ServicePool)
class ServicePoolAdmin(VersionAdmin):
    list_display = ["__str__", "cost"]
    inlines = [EndUserCostAdmin, ITPlatformCostAdmin]

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


@admin.register(models.DivisionITSystem)
class DivisionITSystemAdmin(VersionAdmin):
    list_display = ["it_system", "depends_on_display", "cost_centre", "division", "cost", "cost_estimate"]
    list_filter = ["division", "depends_on"]
    search_fields = ["it_system__name", "it_system__system_id", "cost_centre__name"]
    inlines = [SystemDependencyAdmin]
