from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


HEALTH_CHOICES = (
    ("Recommended", "Recommended"),
    ("Supported", "Supported"),
    ("Constrained", "Constrained"),
    ("High risk", "High risk"),
)
DEPENDENCY_TYPE_CHOICES = (
    ("Service", "Service"),
    ("Compute", "Compute"),
    ("Storage", "Storage"),
    ("Proxy", "Proxy"),
)


def limit_dependency_content_type_choices():
    """Returns a Django Q object that is used to limit the choices of the Dependency
    content_type ForeignKey field.
    Reference: https://docs.djangoproject.com/en/3.0/ref/models/fields/#django.db.models.ForeignKey.limit_choices_to
    """
    return (
        models.Q(app_label="nginx", model="webapp")
        | models.Q(app_label="nginx", model="webserver")
        | models.Q(app_label="rancher", model="cluster")
        | models.Q(app_label="rancher", model="workload")
        | models.Q(app_label="registers", model="itsystem")
        | models.Q(app_label="status", model="host")
    )


class Dependency(models.Model):
    """This represents an object in the IT Assets database which IT systems depend on to function.
    A dependency might be required by one IT system or by many. It might also have some level of
    risk associated with it.
    """

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    # Business rule: a Dependency object will only be associated with certain other model classes.
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=limit_dependency_content_type_choices,
        help_text="The type of the target object.",
    )
    object_id = models.PositiveIntegerField(
        help_text="The primary key of the target object."
    )
    content_object = GenericForeignKey("content_type", "object_id")
    type = models.CharField(
        max_length=64,
        choices=DEPENDENCY_TYPE_CHOICES,
        help_text="The type/category of this dependency.",
    )
    health = models.CharField(
        max_length=64,
        choices=HEALTH_CHOICES,
        blank=True,
        null=True,
        help_text="A point-in-time assessment of the health of this dependency.",
    )

    class Meta:
        verbose_name_plural = "dependencies"

    def __str__(self):
        return "{} - {} ({})".format(self.content_object, self.type, self.health)


PLATFORM_TIER_CHOICES = (
    ("IaaS", "IaaS"),
    ("PaaS", "PaaS"),
    ("SaaS", "SaaS"),
    ("Standalone", "Standalone"),
)


class Platform(models.Model):
    """This represents a group of dependencies as a single unit which IT systems depend on to function.
    A platform might be required by one IT system or by many, and it is generally the 'main'
    dependency of an IT system. A platform might also have some level of risk associated with it.
    """

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    name = models.CharField(
        max_length=256, unique=True, help_text="A unique name for this platform."
    )
    dependencies = models.ManyToManyField(
        Dependency, blank=True, help_text="Dependencies that make up this platform."
    )
    tier = models.CharField(
        max_length=64, choices=PLATFORM_TIER_CHOICES, help_text="The platform tier."
    )
    health = models.CharField(
        max_length=64,
        choices=HEALTH_CHOICES,
        help_text="A point-in-time assessment of the health of this platform dependency.",
    )

    def __str__(self):
        return "{} - {} ({})".format(self.name, self.tier, self.health)


RISK_CATEGORY_CHOICES = (
    ("Traffic", "Traffic"),
    ("Access", "Access"),
    ("Backups", "Backups"),
    ("Support", "Support"),
    ("Operating System", "Operating System"),
    ("Vulnerability", "Vulnerability"),
    ("Patching", "Patching"),
    ("Contingency plan", "Contingency plan"),
)


def limit_risk_assessment_content_type_choices():
    """Returns a Django Q object that is used to limit the choices of the RiskAssessment
    content_type ForeignKey field.
    Reference: https://docs.djangoproject.com/en/3.0/ref/models/fields/#django.db.models.ForeignKey.limit_choices_to
    """
    return (
        models.Q(app_label="bigpicture", model="dependency")
        | models.Q(app_label="bigpicture", model="platform")
        | models.Q(app_label="registers", model="itsystem")
    )


class RiskAssessment(models.Model):
    """This represents risk of a defined category that has been estimated for an object.
    'Risk' in this context is just an arbitrary number rating (higher equals greater risk).
    """

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    # Business rule: a RiskAssessment object will only be associated with a Dependency, Platform or ITSystem.
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=limit_risk_assessment_content_type_choices,
        help_text="The type of the target object.",
    )
    object_id = models.PositiveIntegerField(
        help_text="The primary key of the target object."
    )
    content_object = GenericForeignKey("content_type", "object_id")
    category = models.CharField(
        max_length=64,
        choices=RISK_CATEGORY_CHOICES,
        help_text="The category which this risk falls into.",
    )
    rating = models.PositiveIntegerField(
        help_text="An arbitrary number rating for the risk (higher equals greater risk)."
    )
    notes = models.TextField(
        blank=True,
        help_text="Supporting evidence and/or context for this risk assessment.",
    )

    class Meta:
        # Business rule: a given content object may only have a single risk assessment for a given category.
        # Risk assessments may change over time, but revisions will be saved using django-reversion.
        unique_together = ("category", "content_type", "object_id")

    def __str__(self):
        return "{} - {} ({})".format(self.content_object, self.category, self.rating)
