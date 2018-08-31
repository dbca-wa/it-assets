from datetime import date
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.html import format_html
from organisation.models import OrgUnit, CostCentre
from registers.models import ITSystem


def field_sum(queryset, fieldname):
    return queryset.aggregate(models.Sum(fieldname))["{}__sum".format(fieldname)]


class CostSummary(models.Model):
    """
    Maintains some fields for summarising costs for an object.
    """
    class Meta:
        abstract = True

    def get_cost_queryset(self):
        """
        Override with appropriate filtering across bills or costs.
        """
        return self.__class__.objects.none()

    def cost(self):
        return field_sum(self.get_cost_queryset(), "cost") or Decimal(0)

    def cost_estimate(self):
        return field_sum(self.get_cost_queryset(), "cost_estimate") or Decimal(0)

    def cost_percentage(self):
        year_cost = self.year.cost()
        if year_cost == Decimal(0):
            return 0
        return round(self.cost() / year_cost * 100, 2)

    cost_percentage.short_description = "Cost/FY %"

    def cost_estimate_percentage(self):
        year_cost_est = self.year.cost_estimate()
        if year_cost_est == Decimal(0):
            return 0
        return round(self.cost_estimate() / year_cost_est * 100, 2)

    cost_estimate_percentage.short_description = "Estimate/FY %"

    @property
    def year(self):
        """Always return the newest (current) FY.
        """
        return FinancialYear.objects.first()


class FinancialYear(CostSummary):
    """
    Maintains a running total for the full cost of a year
    Totals are used to calculate percentage values of costs for invoicing
    """
    start = models.DateField()
    end = models.DateField()

    class Meta:
        ordering = ("end",)

    def __str__(self):
        return "{}/{}".format(self.start.year, self.end.year)

    def get_cost_queryset(self):
        return self.bill_set.filter(active=True)


class Contract(CostSummary):
    """
    Maintains the cost of a vendor contract.
    """
    vendor = models.CharField(max_length=320)
    brand = models.CharField(max_length=320, default="N/A")
    reference = models.CharField(max_length=320, default="N/A")
    invoice_period = models.CharField(max_length=320, default="Annual")
    start = models.DateField(default=date.today)
    end = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ('vendor',)

    def __str__(self):
        return "{} ({})".format(self.vendor, self.reference)

    def get_cost_queryset(self):
        return self.bill_set.filter(active=True)


class Bill(models.Model):
    """
    As Bills are updated they should propagate totals for the financial year
    """
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT)
    name = models.CharField(max_length=320, help_text="Product or Service")
    description = models.TextField(default="N/A")
    comment = models.TextField(blank=True, default="")
    quantity = models.CharField(max_length=320, default="1")
    year = models.ForeignKey(FinancialYear, on_delete=models.PROTECT)
    renewal_date = models.DateField(null=True, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_estimate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-cost_estimate",)

    def __str__(self):
        return self.name

    def allocated(self):
        return field_sum(self.cost_items.all(), "percentage") or 0

    def post_save(self):
        # Recalculate child cost values.
        for cost in EndUserCost.objects.filter(bill=self):
            cost.save()
        for cost in ITPlatformCost.objects.filter(bill=self):
            cost.save()


class ServicePool(CostSummary):
    """
    ServicePool used for reporting
    """
    name = models.CharField(max_length=320, editable=False, unique=True)

    def __str__(self):
        return self.name


class Cost(CostSummary):
    name = models.CharField(max_length=320)
    bill = models.ForeignKey(Bill, related_name="cost_items", on_delete=models.PROTECT)
    service_pool = models.ForeignKey(ServicePool, on_delete=models.PROTECT)
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)])
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    cost_estimate = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)

    class Meta:
        ordering = ("-percentage",)

    def __str__(self):
        return self.name

    def pre_save(self):
        if not self.bill.active:
            self.cost, self.cost_estimate = 0, 0
        self.cost = self.bill.cost * self.percentage / Decimal(100)
        self.cost_estimate = self.bill.cost_estimate * self.percentage / Decimal(100)


class Division(CostSummary):
    """
    A Tier 2 Division in the department
    """
    org_unit = models.ForeignKey(OrgUnit, on_delete=models.PROTECT)
    user_count = models.PositiveIntegerField(default=0)
    position = models.PositiveIntegerField(unique=True)

    class Meta:
        ordering = ('position',)

    def __str__(self):
        return self.org_unit.name

    def cc_count(self):
        return self.costcentrelink_set.count()

    def system_count(self):
        return self.systems_by_cc().count()

    def enduser_cost(self):
        total = Decimal(0)
        for service in self.enduserservice_set.all():
            total += round(Decimal(self.user_count) / Decimal(service.total_user_count()) * service.cost(), 2)
        return total

    def enduser_estimate(self):
        total = Decimal(0)
        for service in self.enduserservice_set.all():
            total += round(Decimal(self.user_count) / Decimal(service.total_user_count()) * service.cost_estimate(), 2)
        return total

    def system_cost(self):
        return sum(system.cost() for system in self.systems_by_cc().all())

    def system_cost_estimate(self):
        return sum(system.cost_estimate() for system in self.systems_by_cc().all())

    def cost(self):
        return self.enduser_cost() + self.system_cost()

    def cost_estimate(self):
        return self.enduser_estimate() + self.system_cost_estimate()

    def systems_by_cc(self):
        return self.divisionitsystem_set.filter(systemdependency__isnull=False).order_by("cost_centre__cc__name", "it_system__name").distinct()

    def bill(self):
        return format_html('<a href="{}?division={}" target="_blank">Bill</a>', reverse('recoup_bill'), self.pk)

    def user_count_percentage(self):
        return round(self.user_count / field_sum(Division.objects.all(), 'user_count') * 100, 2)


class CostCentreLink(models.Model):
    """Link table between CC, division and user count.
    """
    cc = models.ForeignKey(CostCentre, on_delete=models.PROTECT)
    division = models.ForeignKey(Division, on_delete=models.PROTECT)
    user_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.cc.code

    class Meta:
        ordering = ('cc__name',)

    def systems(self):
        return self.divisionitsystem_set.filter(systemdependency__isnull=False).distinct()

    def system_count(self):
        return self.systems().count()

    def system_cost(self):
        return sum(system.cost() for system in self.systems())

    def system_cost_estimate(self):
        return sum(system.cost_estimate() for system in self.systems())

    def user_count_percentage(self):
        return round(self.user_count / field_sum(Division.objects.all(), 'user_count') * 100, 2)

    def post_save(self):
        self.division.user_count = field_sum(self.division.costcentrelink_set.all(), "user_count")
        if self.division.user_count > 0:
            self.division.save()


class EndUserService(CostSummary):
    """
    Grouping used to simplify linkages of costs to divisions, and for reporting.
    """
    name = models.CharField(max_length=320)
    divisions = models.ManyToManyField(Division)

    def __str__(self):
        return self.name

    def total_user_count(self):
        return field_sum(self.divisions, "user_count")

    def get_cost_queryset(self):
        return self.endusercost_set.filter()


class EndUserCost(Cost):
    """
    Broken down cost for end users
    """
    service = models.ForeignKey(EndUserService, on_delete=models.PROTECT)


class ITPlatform(CostSummary):
    """
    Platform or Infrastructure IT systems depend on
    Grouping used to simplify linkages of costs to systems, and for reporting
    Note a system may have to have its own unique systemdependency
    """
    name = models.CharField(max_length=320)

    class Meta:
        verbose_name = "IT platform"

    def __str__(self):
        return self.name

    def system_count(self):
        return self.systemdependency_set.count()

    def system_weight_total(self):
        return field_sum(self.systemdependency_set, "weighting")

    def get_cost_queryset(self):
        return self.itplatformcost_set.all()


class ITPlatformCost(Cost):
    """
    Broken down cost for IT component
    """
    platform = models.ForeignKey(ITPlatform, on_delete=models.PROTECT)


class DivisionITSystem(CostSummary):
    """
    A system owned by a division, that shares the cost of a set of service groups
    """
    cost_centre = models.ForeignKey(CostCentreLink, null=True, on_delete=models.PROTECT)
    it_system = models.ForeignKey(ITSystem, on_delete=models.PROTECT)
    division = models.ForeignKey(Division, on_delete=models.PROTECT)
    depends_on = models.ManyToManyField(ITPlatform, through="SystemDependency")

    class Meta:
        ordering = ('cost_centre__cc__name', 'it_system__name')
        verbose_name = "Division IT System"

    def __str__(self):
        return "{} (#{})".format(self.it_system.name, self.it_system.system_id)

    def cost(self):
        total = Decimal(0)
        for dep in self.systemdependency_set.all():
            total += dep.platform.cost() * Decimal(dep.weighting / dep.platform.system_weight_total())
        return round(total, 2)

    def cost_estimate(self):
        total = Decimal(0)
        for dep in self.systemdependency_set.all():
            total += dep.platform.cost_estimate() * Decimal(dep.weighting / dep.platform.system_weight_total())
        return round(total, 2)

    def depends_on_display(self):
        return ", ".join(str(p) for p in self.depends_on.all())

    def pre_save(self):
        self.division = self.cost_centre.division


class SystemDependency(CostSummary):
    """
    Links a system to the platforms that it depends on.
    """
    system = models.ForeignKey(DivisionITSystem, on_delete=models.PROTECT)
    platform = models.ForeignKey(ITPlatform, on_delete=models.PROTECT)
    weighting = models.FloatField(default=1)

    class Meta:
        unique_together = (("system", "platform"),)

    def __str__(self):
        return "{} depends on {}".format(self.system, self.platform)

    def post_save(self):
        self.platform.system_count = self.platform.systemdependency_set.count()
        self.platform.save()


@receiver(post_save)
def post_save_hook(sender, instance, **kwargs):
    if 'raw' in kwargs and kwargs['raw']:
        return
    if (hasattr(instance, "post_save")):
        instance.post_save()


@receiver(pre_save)
def pre_save_hook(sender, instance, **kwargs):
    if 'raw' in kwargs and kwargs['raw']:
        return
    if (hasattr(instance, "pre_save")):
        instance.pre_save()
