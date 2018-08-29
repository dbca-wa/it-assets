from datetime import date
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from organisation.models import OrgUnit, CostCentre
from registers.models import ITSystem


class FinancialYear(models.Model):
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


class Contract(models.Model):
    """
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


class ServicePool(models.Model):
    """
    ServicePool used for reporting
    """
    name = models.CharField(max_length=320, editable=False, unique=True)

    def __str__(self):
        return self.name


class Cost(models.Model):
    """
    """
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


class Division(models.Model):
    """
    A Tier 2 Division in the department
    """
    org_unit = models.ForeignKey(OrgUnit, on_delete=models.PROTECT)
    user_count = models.PositiveIntegerField(default=0)
    position = models.PositiveIntegerField(unique=True)

    class Meta:
        ordering = ('position',)

    def __str__(self):
        return self.org_unit


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


class EndUserService(models.Model):
    """
    Grouping used to simplify linkages of costs to divisions, and for reporting.
    """
    name = models.CharField(max_length=320)
    divisions = models.ManyToManyField(Division)

    def __str__(self):
        return self.name


class EndUserCost(Cost):
    """
    Broken down cost for end users
    """
    service = models.ForeignKey(EndUserService, on_delete=models.PROTECT)


class ITPlatform(models.Model):
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


class ITPlatformCost(Cost):
    """
    Broken down cost for IT component
    """
    platform = models.ForeignKey(ITPlatform, on_delete=models.PROTECT)


class DivisionITSystem(models.Model):
    """
    A system owned by a division, that shares the cost of a set of service groups
    """
    cost_centre = models.ForeignKey(CostCentreLink, null=True, on_delete=models.PROTECT)
    it_system = models.ForeignKey(ITSystem, on_delete=models.PROTECT)
    division = models.ForeignKey(Division, on_delete=models.PROTECT)
    depends_on = models.ManyToManyField(ITPlatform, through="SystemDependency")

    def __str__(self):
        return "{} (#{})".format(self.it_system.name, self.it_system.system_id)

    class Meta:
        ordering = ('cost_centre__name', 'it_system__name')


class SystemDependency(models.Model):
    """
    Links a system to the platforms that it depends on.
    """
    system = models.ForeignKey(DivisionITSystem, on_delete=models.PROTECT)
    platform = models.ForeignKey(ITPlatform, on_delete=models.PROTECT)
    weighting = models.FloatField(default=1)


    def __str__(self):
        return "{} depends on {}".format(self.system, self.platform)

    class Meta:
        unique_together = (("system", "platform"),)
