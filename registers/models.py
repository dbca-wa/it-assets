from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django import forms
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone
from django.utils.safestring import mark_safe

from organisation.models import CommonFields, DepartmentUser, Location
from tracking.models import Computer
from registers.utils import smart_truncate


CRITICALITY_CHOICES = (
    (1, 'Critical'),
    (2, 'Moderate'),
    (3, 'Low'),
)
IMPORTANCE_CHOICES = (
    (1, 'High'),
    (2, 'Medium'),
    (3, 'Low'),
)
DOC_STATUS_CHOICES = (
    (1, 'Draft'),
    (2, 'Released'),
    (3, 'Superseded'),
)


class ChoiceArrayField(ArrayField):
    """A field that allows us to store an array of choices.
    Uses Django's postgres ArrayField and a MultipleChoiceField for its formfield.
    Source:
    https://blogs.gnome.org/danni/2016/03/08/multiple-choice-using-djangos-postgres-arrayfield/
    """
    def formfield(self, **kwargs):
        defaults = {
            'form_class': forms.MultipleChoiceField,
            'choices': self.base_field.choices,
        }
        defaults.update(kwargs)
        return super(ArrayField, self).formfield(**defaults)


class UserGroup(models.Model):
    """A model to represent an arbitrary group of users for an IT System.
    E.g. 'All department staff', 'External govt agency staff', etc.
    """
    name = models.CharField(max_length=2048, unique=True)
    user_count = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return '{} ({})'.format(self.name, self.user_count)


class ITSystemHardware(models.Model):
    """A model to represent the relationship between IT Systems and Computers,
    i.e. what role each Computer serves and which IT System(s) make use of them.
    """
    ROLE_CHOICES = (
        (1, 'Application server'),
        (2, 'Database server'),
        (3, 'Network file storage'),
        (4, 'Reverse proxy'),
        (5, 'Shared workstation'),
    )
    computer = models.ForeignKey(Computer, on_delete=models.PROTECT)
    role = models.PositiveSmallIntegerField(choices=ROLE_CHOICES)
    production = models.BooleanField(
        default=False, help_text='Hardware is used by production IT system.')
    decommissioned = models.BooleanField(
        default=False, help_text='Hardware has been decommissioned?')
    description = models.TextField(blank=True)
    patch_group = models.CharField(
        max_length=256, null=True, blank=True, help_text='Patch group that this host has been placed in.')
    host = models.CharField(
        max_length=256, null=True, blank=True, help_text='Host, or hosting environment.')

    class Meta:
        verbose_name_plural = 'IT System hardware'
        unique_together = ('computer', 'role')
        ordering = ('computer__hostname',)

    def __str__(self):
        if self.production:
            return '{} (prod {})'.format(self.computer.hostname, self.get_role_display().lower())
        else:
            return '{} (non-prod {})'.format(self.computer.hostname, self.get_role_display().lower())

    def set_patch_group(self):
        """Follow relationships (self -> computer -> ec2_instance) to see if
        the patch_group value for this object can be automatically set.
        """
        if self.computer and self.computer.ec2_instance:
            ec2 = self.computer.ec2_instance
            if 'Patch Group' in ec2.tags:
                self.patch_group = ec2.tags['Patch Group']
                self.save()

        return self.patch_group


class Platform(models.Model):
    """A model to represent an IT System Platform Service, as defined in the
    Department IT Strategy.
    """
    PLATFORM_CATEGORY_CHOICES = (
        ('db', 'Database'),
        ('dns', 'DNS'),
        ('email', 'Email'),
        ('idam', 'Identity & access management'),
        ('middle', 'Middleware'),
        ('phone', 'Phone system'),
        ('proxy', 'Reverse proxy'),
        ('storage', 'Storage'),
        ('vpn', 'VPN'),
        ('vm', 'Virtualisation'),
        ('web', 'Web server'),
    )
    category = models.CharField(max_length=64, choices=PLATFORM_CATEGORY_CHOICES, db_index=True)
    name = models.CharField(max_length=512)

    class Meta:
        ordering = ('category', 'name')
        unique_together = ('category', 'name')

    def __str__(self):
        return '{} - {}'.format(self.get_category_display(), self.name)


class ITSystem(CommonFields):
    """Represents a named system providing a package of functionality to
    Department staff (normally vendor or bespoke software), which is supported
    by OIM and/or an external vendor.
    """
    STATUS_CHOICES = (
        (0, 'Production'),
        (1, 'Development'),
        (2, 'Production (Legacy)'),
        (3, 'Decommissioned'),
        (4, 'Unknown')
    )
    ACCESS_CHOICES = (
        (1, 'Public Internet'),
        (2, 'Authenticated Extranet'),
        (3, 'Corporate Network'),
        (4, 'Local System (Networked)'),
        (5, 'Local System (Standalone)')
    )
    AUTHENTICATION_CHOICES = (
        (1, 'Domain/application Credentials'),
        (2, 'Single Sign On'),
        (3, 'Externally Managed')
    )
    AVAILABILITY_CHOICES = (
        (1, '24 hours a day, 7 days a week, 365 days a year'),
        (2, 'Department core business hours'),
    )
    SYSTEM_TYPE_CHOICES = (
        (1, 'System - Web application'),
        (2, 'System - Client application'),
        (3, 'System - Mobile application'),
        (5, 'System - Externally hosted application'),
        (4, 'Service'),
        (6, 'Platform'),
        (7, 'Infrastructure'),
    )
    HEALTH_CHOICES = (
        (0, 'Healthy'),
        (1, 'Issues noted'),
        (2, 'At risk'),
    )
    RISK_CHOICES = (
        ('0', 'IT System features not aligned to business processes'),
        ('1', 'IT System technology refresh lifecycle not safeguarded or future-proofed'),
        ('2', 'IT System data/information integrity and availability not aligned to business processes'),
        ('3', 'IT System emergency contingency and disaster recovery approach not well established'),
        ('4', 'IT System support arrangements not well established, value for money and/or safeguarded'),
        ('5', 'IT System roles and responsibilities not well established'),
        ('6', 'IT System solution design not aligned to department IT standards'),
        ('7', 'IT System change management does not consistently consider risk and security'),
        ('8', 'IT System incident and security management not triaged on business criticality'),
        ('9', 'IT System user training not well established'),
    )
    FUNCTION_CHOICES = (
        ('0', 'Planning'),
        ('1', 'Operation'),
        ('2', 'Reporting'),
    )
    USE_CHOICES = (
        ('0', 'Measurement'),
        ('1', 'Information'),
        ('2', 'Wisdom'),
        ('3', 'Data'),
        ('4', 'Knowledge'),
        ('5', 'Intelligence'),
    )
    CAPABILITY_CHOICES = (
        ('0', 'Information lifecycle'),
        ('1', 'Communication and collaboration'),
        ('2', 'Automation and integration'),
        ('3', 'Security and risk management'),
        ('4', 'Intelligence and analytics'),
    )

    name = models.CharField(max_length=128, unique=True)
    system_id = models.CharField(
        max_length=16, unique=True, verbose_name='system ID')
    acronym = models.CharField(max_length=16, null=True, blank=True)
    status = models.PositiveSmallIntegerField(
        choices=STATUS_CHOICES, default=4)
    status_display = models.CharField(
        max_length=128, null=True, editable=False)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, null=True,
        related_name='systems_owned', help_text='Application owner')
    custodian = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, null=True,
        related_name='systems_custodianed', help_text='Application custodian')
    data_custodian = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, null=True, blank=True,
        related_name='systems_data_custodianed', help_text='Application data custodian')
    preferred_contact = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, null=True, blank=True,
        related_name='systems_preferred_contact')
    link = models.CharField(
        max_length=2048, null=True, blank=True,
        help_text='URL to web application')
    documentation = models.URLField(
        max_length=2048, null=True, blank=True,
        help_text='URL to end-user documentation')
    technical_documentation = models.URLField(
        max_length=2048, null=True, blank=True,
        help_text='URL to technical documentation')
    status_html = models.URLField(
        max_length=2048, null=True, blank=True,
        help_text='URL to status/uptime info')
    authentication = models.PositiveSmallIntegerField(
        choices=AUTHENTICATION_CHOICES, default=1,
        help_text='The method by which users authenticate themselve to the system.')
    authentication_display = models.CharField(
        max_length=128, null=True, editable=False)
    access = models.PositiveSmallIntegerField(
        choices=ACCESS_CHOICES, default=3,
        help_text='The network upon which this system is accessible.')
    access_display = models.CharField(
        max_length=128, null=True, editable=False)
    request_access = models.TextField(
        blank=True, help_text='Procedure to request access to this application')
    criticality = models.PositiveIntegerField(
        choices=CRITICALITY_CHOICES, null=True, blank=True,
        help_text='How critical is this system to P&W core functions?')
    criticality_display = models.CharField(
        max_length=128, null=True, editable=False)
    availability = models.PositiveIntegerField(
        choices=AVAILABILITY_CHOICES, null=True, blank=True,
        help_text='Expected availability for this IT System')
    availability_display = models.CharField(
        max_length=128, null=True, editable=False)
    schema_url = models.URLField(
        max_length=2048, null=True, blank=True,
        help_text='URL to schema diagram')
    user_groups = models.ManyToManyField(
        UserGroup, blank=True, help_text='User group(s) that use this IT System')
    hardwares = models.ManyToManyField(
        ITSystemHardware, blank=True, verbose_name='hardware',
        help_text='Hardware that is used to provide this IT System')
    bh_support = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, null=True, blank=True, related_name='bh_support',
        verbose_name='business hours support', help_text='Business hours support contact')
    ah_support = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, null=True, blank=True, related_name='ah_support',
        verbose_name='after hours support', help_text='After-hours support contact')
    system_reqs = models.TextField(
        blank=True,
        help_text='A written description of the requirements to use the system (e.g. web browser version)')
    system_type = models.PositiveSmallIntegerField(
        choices=SYSTEM_TYPE_CHOICES, null=True, blank=True)
    system_type_display = models.CharField(
        max_length=128, null=True, editable=False)
    vulnerability_docs = models.URLField(
        max_length=2048, null=True, blank=True,
        help_text='URL to documentation related to known vulnerability reports')
    workaround = models.TextField(
        blank=True, help_text='Written procedure for users to work around an outage of this system')
    recovery_docs = models.URLField(
        max_length=2048, null=True, blank=True,
        help_text='URL to recovery procedure(s) in the event of system failure')
    mtd = models.DurationField(
        help_text='Maximum Tolerable Downtime (days hh:mm:ss)',
        default=timedelta(days=14))
    rto = models.DurationField(
        help_text='Recovery Time Objective (days hh:mm:ss)',
        default=timedelta(days=7))
    rpo = models.DurationField(
        help_text='Recovery Point Objective/Data Loss Interval (days hh:mm:ss)',
        default=timedelta(hours=24))
    contingency_plan = models.FileField(
        blank=True, null=True, max_length=255, upload_to='uploads/%Y/%m/%d')
    contingency_plan_status = models.PositiveIntegerField(
        choices=DOC_STATUS_CHOICES, null=True, blank=True)
    contingency_plan_last_tested = models.DateField(
        null=True, blank=True, help_text='Date that the plan was last tested.')
    notes = models.TextField(blank=True, null=True)
    system_health = models.PositiveIntegerField(
        choices=HEALTH_CHOICES, null=True, blank=True)
    system_creation_date = models.DateField(
        null=True, blank=True,
        help_text='Date that this system went into production.')
    risks = ChoiceArrayField(
        null=True, blank=True,
        base_field=models.CharField(max_length=256, choices=RISK_CHOICES), default=list,
        verbose_name='IT System risks')
    backup_info = models.TextField(
        null=True, blank=True, verbose_name='backup information',
        help_text="Information about the backup/archiving of this system's data.")
    critical_period = models.CharField(
        max_length=255, null=True, blank=True,
        help_text='Is there a period/season when this system is most important?')
    alt_processing = models.TextField(
        null=True, blank=True, verbose_name='alternate processing procedure')
    technical_recov = models.TextField(
        null=True, blank=True, verbose_name='technical recovery procedure')
    post_recovery = models.TextField(
        null=True, blank=True, verbose_name='post recovery procedure',
        help_text='Functional testing and post recovery procedure.')
    variation_iscp = models.TextField(
        null=True, blank=True, verbose_name='Variation to the ISCP')
    user_notification = models.TextField(
        null=True, blank=True,
        help_text='List of users/stakeholders to contact regarding incidents')
    function = ChoiceArrayField(
        null=True, blank=True,
        base_field=models.CharField(max_length=256, choices=FUNCTION_CHOICES), default=list,
        verbose_name='IT System function(s)')
    use = ChoiceArrayField(
        null=True, blank=True,
        base_field=models.CharField(max_length=256, choices=USE_CHOICES), default=list,
        verbose_name='IT System use(s)')
    capability = ChoiceArrayField(
        null=True, blank=True,
        base_field=models.CharField(max_length=256, choices=CAPABILITY_CHOICES), default=list,
        verbose_name='IT System capabilities')
    unique_evidence = models.NullBooleanField(
        default=None, help_text='''Is the digital content kept in this business'''
        ''' system unique evidence of the official business of the Department?''')
    point_of_truth = models.NullBooleanField(
        default=None, help_text='''Is the digital content kept in this business'''
        ''' system a single point of truth?''')
    legal_need_to_retain = models.NullBooleanField(
        default=None, help_text='''Is there a legal or compliance need to keep'''
        ''' the digital content in this system?''')
    other_projects = models.TextField(
        null=True, blank=True,
        help_text='Details of related IT Systems and projects.')
    sla = models.TextField(
        null=True, blank=True, verbose_name='Service Level Agreement',
        help_text='''Details of any Service Level Agreement that exists for'''
        ''' this IT System (typically with an external vendor).''')
    biller_code = models.CharField(
        max_length=64, null=True, blank=True,
        help_text='BPAY biller code for this IT System (must be unique).')
    oim_internal_only = models.BooleanField(
        default=False, help_text='For OIM use only')
    platforms = models.ManyToManyField(Platform, blank=True)

    class Meta:
        verbose_name = 'IT System'
        ordering = ('name',)

    def __init__(self, *args, **kwargs):
        super(ITSystem, self).__init__(*args, **kwargs)
        # Store the pre-save values of some fields on object init.
        self.__original_contingency_plan = self.contingency_plan

    def __str__(self):
        return self.name

    def description_html(self):
        return mark_safe(self.description)

    def save(self, *args, **kwargs):
        if not self.system_id:
            self.system_id = 'S{0:03d}'.format(
                ITSystem.objects.order_by('-pk').first().pk + 1)
        self.status_display = self.get_status_display()
        self.authentication_display = self.get_authentication_display()
        if not self.link:  # systems with no link default to device
            self.access = 4
        self.access_display = self.get_access_display()
        self.criticality_display = self.get_criticality_display()
        self.availability_display = self.get_availability_display()
        self.system_type_display = self.get_system_type_display()
        # Note that biller_code uniqueness is checked in the admin ModelForm.
        super(ITSystem, self).save(*args, **kwargs)

    @property
    def division_name(self):
        if self.cost_centre and self.cost_centre.division:
            return self.cost_centre.division.name
        else:
            return ''


class ITSystemDependency(models.Model):
    """A model to represent a dependency that an ITSystem has on another, plus
    the criticality of that dependency.
    """
    itsystem = models.ForeignKey(
        ITSystem, on_delete=models.PROTECT, verbose_name='IT System',
        help_text='The IT System')
    dependency = models.ForeignKey(
        ITSystem, on_delete=models.PROTECT, related_name='dependency',
        help_text='The system which is depended upon by the IT System')
    criticality = models.PositiveIntegerField(
        choices=CRITICALITY_CHOICES, help_text='How critical is the dependency?')
    description = models.TextField(
        null=True, blank=True, help_text='Details of the dependency, its criticality, any workarounds, etc.')

    class Meta:
        verbose_name = 'IT System dependency'
        verbose_name_plural = 'IT System dependencies'
        unique_together = ('itsystem', 'dependency')
        ordering = ('itsystem__name', 'criticality')

    def __str__(self):
        return '{} - {} ({})'.format(
            self.itsystem.name, self.dependency.name, self.get_criticality_display())


class Backup(CommonFields):
    """Represents the details of backup & recovery arrangements for a single
    piece of computing hardware.
    """
    ROLE_CHOICES = (
        (0, 'Generic Server'),
        (1, 'Domain Controller'),
        (2, 'Database Server'),
        (3, 'Application Host'),
        (4, 'Management Server'),
        (5, 'Site Server'),
        (6, 'File Server'),
        (7, 'Print Server'),
        (8, 'Block Storage Server'),
        (9, 'Email Server'),
        (10, 'Network Device'))
    STATUS_CHOICES = (
        (0, 'Production'),
        (1, 'Pre-Production'),
        (2, 'Legacy'),
        (3, 'Decommissioned')
    )
    SCHEDULE_CHOICES = (
        (0, 'Manual'),
        (1, 'Point in time, 7 day retention'),
        (2, 'Daily, 7 day retention'),
        (3, 'Daily, 30 day retention'),
        (4, 'Weekly, 1 month retention')
    )
    computer = models.ForeignKey(
        Computer, on_delete=models.PROTECT, null=True, blank=True)
    operating_system = models.CharField(max_length=120)
    role = models.PositiveSmallIntegerField(choices=ROLE_CHOICES, default=0)
    status = models.PositiveSmallIntegerField(
        choices=STATUS_CHOICES, default=0)
    database_backup = models.CharField(
        max_length=2048, null=True, blank=True,
        help_text='URL to Database backup/restore/logs info')
    database_schedule = models.PositiveSmallIntegerField(
        choices=SCHEDULE_CHOICES, default=0)
    filesystem_backup = models.CharField(
        max_length=2048, null=True, blank=True,
        help_text='URL to Filesystem backup/restore/logs info')
    filesystem_schedule = models.PositiveSmallIntegerField(
        choices=SCHEDULE_CHOICES, default=0)
    appdata_backup = models.CharField(
        max_length=2048, null=True, blank=True,
        help_text='URL to Application Data backup/restore/logs info')
    appdata_schedule = models.PositiveSmallIntegerField(
        choices=SCHEDULE_CHOICES, default=0)
    appconfig_backup = models.CharField(
        max_length=2048, null=True, blank=True,
        help_text='URL to Config for App/Server')
    appconfig_schedule = models.PositiveSmallIntegerField(
        choices=SCHEDULE_CHOICES, default=0)
    os_backup = models.CharField(
        max_length=2048, null=True, blank=True,
        help_text='URL to Build Documentation')
    os_schedule = models.PositiveSmallIntegerField(
        choices=SCHEDULE_CHOICES, default=0)
    last_tested = models.DateField(
        null=True, blank=True, help_text='Last tested date')
    test_schedule = models.PositiveSmallIntegerField(
        default=12, help_text='Test Schedule in Months, 0 for never')
    comment = models.TextField(blank=True)

    def next_test_date(self):
        if self.test_schedule == 0:
            return 'NO TESTING REQUIRED'
        if not self.last_tested:
            return 'NEVER TESTED'
        else:
            return self.last_tested + relativedelta(months=self.test_schedule)

    def test_overdue(self):
        if self.test_schedule == 0:
            return False
        if not self.last_tested:
            return True
        return self.next_test_date() < timezone.now().date()

    def __str__(self):
        if self.computer:
            return '{} ({})'.format(self.computer.hostname.split(
                '.')[0], self.get_status_display())
        else:
            return self.get_status_display()

    class Meta:
        ordering = ('computer__hostname',)


class BusinessService(models.Model):
    """Represents the Department's core business services.
    """
    number = models.PositiveIntegerField(
        unique=True, help_text='Service number')
    name = models.CharField(max_length=256, unique=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ('number',)

    def __str__(self):
        return 'Service {}: {}'.format(self.number, self.name)


class BusinessFunction(models.Model):
    """Represents a function of the Department, undertaken to meet the
    Department's core services. Each function must be linked to 1+
    BusinessService object.
    """
    name = models.CharField(max_length=256, unique=True)
    description = models.TextField(null=True, blank=True)
    services = models.ManyToManyField(BusinessService)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class BusinessProcess(models.Model):
    """Represents a business process that the Department undertakes in order
    to fulfil one of the Department's functions.
    """
    name = models.CharField(max_length=256, unique=True)
    description = models.TextField(null=True, blank=True)
    functions = models.ManyToManyField(BusinessFunction)
    criticality = models.PositiveIntegerField(
        choices=CRITICALITY_CHOICES, null=True, blank=True,
        help_text='How critical is the process?')

    class Meta:
        verbose_name_plural = 'business processes'
        ordering = ('name',)

    def __str__(self):
        return self.name


class ProcessITSystemRelationship(models.Model):
    """A model to represent the relationship between a BusinessProcess and an
    ITSystem object.
    """
    process = models.ForeignKey(BusinessProcess, on_delete=models.PROTECT)
    itsystem = models.ForeignKey(ITSystem, on_delete=models.PROTECT)
    importance = models.PositiveIntegerField(
        choices=IMPORTANCE_CHOICES,
        help_text='How important is the IT System to undertaking this process?')

    class Meta:
        unique_together = ('process', 'itsystem')
        verbose_name_plural = 'Process/IT System relationships'

    def __str__(self):
        return '{} - {} ({})'.format(
            self.itsystem.name, self.process.name, self.get_importance_display())


class ITSystemEvent(models.Model):
    """Represents information about an event that affects one or more IT Systems
    or networked locations.
    """
    EVENT_TYPE_CHOICES = (
        (1, 'Incident'),
        (2, 'Maintenance'),
        (3, 'Information'),
    )
    event_type = models.PositiveSmallIntegerField(choices=EVENT_TYPE_CHOICES)
    description = models.TextField()
    planned = models.BooleanField(default=False, help_text='Was this event planned?')
    start = models.DateTimeField(help_text='Event start (date & time)')
    duration = models.DurationField(null=True, blank=True, help_text='Optional: duration of the event (hh:mm:ss).')
    end = models.DateTimeField(null=True, blank=True, help_text='Optional: event end (date & time)')
    current = models.BooleanField(default=True, editable=False)
    it_systems = models.ManyToManyField(ITSystem, blank=True, help_text='IT System(s) affect by this event')
    locations = models.ManyToManyField(Location, blank=True, help_text='Location(s) affect by this event')
    # TODO: incident type (optional: P1, P2, P3, P4)
    # TODO: FD ticket (optional)

    class Meta:
        verbose_name = 'IT System event'

    def __str__(self):
        return '{}: {}'.format(self.get_event_type_display(), smart_truncate(self.description))

    def save(self, *args, **kwargs):
        # On save, set the `current` boolean field value correctly for the this instant.
        # An event needs either an end datestamp and/or a duration to set `current`.
        if self.end and self.end < timezone.now():
            self.current = False
        elif self.duration and (self.start + self.duration) < timezone.now():
            self.current = False
        else:
            self.current = True
        super(ITSystemEvent, self).save(*args, **kwargs)
