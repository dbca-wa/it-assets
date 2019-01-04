from django import forms
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives
from django.db import models
from django.urls import reverse
from os import path

from organisation.models import CommonFields, DepartmentUser, Location
from tracking.models import Computer
from .utils import smart_truncate


CRITICALITY_CHOICES = (
    (1, 'Critical'),
    (2, 'Moderate'),
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
        (1, '24/7/365'),
        (2, 'Business hours'),
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
    RECOVERY_CATEGORY_CHOICES = (
        (1, 'MTD: 1+ week; RTO: 5+ days'),
        (2, 'MTD: 72 hours; RTO: 48 hours'),
        (3, 'MTD: 8 hours; RTO: 4 hours'),
    )
    SEASONALITY_CHOICES = (
        (1, 'Bushfire season'),
        (2, 'End of financial year'),
        (3, 'Annual reporting'),
        (4, 'School holidays'),
    )
    BACKUP_CHOICES = (
        (1, 'Point in time database with daily local'),
        (2, 'Daily local'),
        (3, 'Vendor-managed'),
    )

    name = models.CharField(max_length=128, unique=True)
    acronym = models.CharField(max_length=16, null=True, blank=True)
    system_id = models.CharField(max_length=16, unique=True, verbose_name='system ID')
    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES, default=4)
    link = models.CharField(
        max_length=2048, null=True, blank=True, help_text='URL to web application')
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, null=True,
        related_name='systems_owned', help_text='IT system owner')
    technology_custodian = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, null=True,
        related_name='systems_tech_custodianed', help_text='Technology custodian')
    information_custodian = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, null=True, blank=True,
        related_name='systems_info_custodianed', help_text='Information custodian')
    bh_support = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, null=True, blank=True, related_name='bh_support',
        verbose_name='business hours support', help_text='Business hours support contact')
    ah_support = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, null=True, blank=True, related_name='ah_support',
        verbose_name='after hours support', help_text='After-hours support contact')
    documentation = models.URLField(
        max_length=2048, null=True, blank=True, help_text='URL to end-user documentation')
    technical_documentation = models.URLField(
        max_length=2048, null=True, blank=True, help_text='URL to technical documentation')
    status_url = models.URLField(
        max_length=2048, null=True, blank=True, verbose_name='status URL',
        help_text='URL to status/uptime info')
    availability = models.PositiveIntegerField(
        choices=AVAILABILITY_CHOICES, null=True, blank=True,
        help_text='Expected availability for this system')
    user_groups = models.ManyToManyField(
        UserGroup, blank=True, help_text='User group(s) that use this system')
    application_server = models.TextField(
        blank=True, help_text='Application server(s) that host this system')
    database_server = models.TextField(
        blank=True, help_text="Database server(s) that host this system's data")
    network_storage = models.TextField(
        blank=True, help_text='Network storage location(s) used by this system')
    backups = models.PositiveIntegerField(
        choices=BACKUP_CHOICES, null=True, blank=True,
        help_text='Data backup arrangements for this system')
    system_reqs = models.TextField(
        blank=True, verbose_name='system requirements',
        help_text='A written description of the requirements to use the system (e.g. web browser version)')
    recovery_category = models.PositiveIntegerField(
        choices=RECOVERY_CATEGORY_CHOICES, null=True, blank=True,
        help_text='The recovery requirements for this system')
    seasonality = models.PositiveIntegerField(
        choices=SEASONALITY_CHOICES, null=True, blank=True,
        help_text='Season/period when this system is most important')
    user_notification = models.EmailField(
        null=True, blank=True,
        help_text='Users (group email address) to be advised of any changes (outage or upgrade) to the system')
    emergency_operations = models.BooleanField(
        default=False, help_text='System is used for emergency operations')
    online_bookings = models.BooleanField(
        default=False, help_text='System is used for online bookings')
    visitor_safety = models.BooleanField(
        default=False, help_text='System is used for visitor safety')
    authentication = models.PositiveSmallIntegerField(
        choices=AUTHENTICATION_CHOICES, default=1, null=True, blank=True,
        help_text='The method by which users authenticate themselve to the system.')
    access = models.PositiveSmallIntegerField(
        choices=ACCESS_CHOICES, default=3, null=True, blank=True,
        help_text='The network upon which this system is accessible.')
    platforms = models.ManyToManyField(Platform, blank=True)
    hardwares = models.ManyToManyField(
        ITSystemHardware, blank=True, verbose_name='hardware',
        help_text='[DEPRECATED] Hardware that is used to provide this system')
    system_type = models.PositiveSmallIntegerField(
        choices=SYSTEM_TYPE_CHOICES, null=True, blank=True)
    oim_internal_only = models.BooleanField(
        default=False, verbose_name='OIM internal only', help_text='For OIM use only')
    biller_code = models.CharField(
        max_length=64, null=True, blank=True,
        help_text='BPAY biller code for this system (must be unique).')

    class Meta:
        verbose_name = 'IT System'
        ordering = ('name',)

    def __str__(self):
        return self.name

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


class Incident(models.Model):
    """Represents an ITIL incident that affects one or more IT Systems, services or locations.
    """
    PRIORITY_CHOICES = (
        ('L0', 'Low - L0'),
        ('L1', 'Moderate - L1'),
        ('L2', 'High - L2'),
        ('L3', 'Critical - L3'),
    )
    RTO = {
        # Recovery Time Objectives (seconds).
        'L0': 60 * 60 * 100,
        'L1': 60 * 60 * 20,
        'L2': 60 * 60 * 4,
        'L3': 60 * 60 * 2,
    }
    DETECTION_CHOICES = (
        (0, 'Monitoring process'),
        (1, 'OIM staff report'),
        (2, 'User/custodian report'),
    )
    CATEGORY_CHOICES = (
        (0, 'Outage'),
        (1, 'Service degredation'),
        (2, 'Security'),
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    description = models.TextField(help_text='Short description of the incident')
    priority = models.CharField(max_length=16, choices=PRIORITY_CHOICES, db_index=True)
    start = models.DateTimeField(help_text='Initial detection time')
    resolution = models.DateTimeField(null=True, blank=True, help_text='Resolution time')
    it_systems = models.ManyToManyField(
        ITSystem, blank=True, verbose_name='IT Systems', help_text='IT System(s) affected')
    locations = models.ManyToManyField(
        Location, blank=True, help_text='Location(s) affected (leave unselected to imply "all locations")')
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='manager',
        help_text='Incident manager')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='owner',
        help_text='Incident owner')
    url = models.URLField(
        max_length=2048, null=True, blank=True, verbose_name='URL',
        help_text='Incident report URL (e.g. Freshdesk ticket)', )
    detection = models.PositiveIntegerField(
        blank=True, null=True, choices=DETECTION_CHOICES, db_index=True,
        help_text='The method by which the incident was initially detected')
    category = models.PositiveIntegerField(blank=True, null=True, db_index=True, choices=CATEGORY_CHOICES)
    workaround = models.TextField(
        null=True, blank=True, help_text='Workaround/business continuity actions performed')
    root_cause = models.TextField(null=True, blank=True, help_text='Root cause analysis/summary')
    remediation = models.TextField(
        null=True, blank=True, help_text='Remediation/improvement actions performed/planned')
    pir = models.FileField(
        null=True, blank=True, upload_to='uploads/%Y/%m/%d', help_text='Post-incident review (attachment)')

    class Meta:
        ordering = ('-created',)

    def __str__(self):
        if self.category is not None:
            return '{} ({}, {})'.format(self.pk, self.get_priority_display(), self.get_category_display())
        return '{} ({})'.format(self.pk, self.get_priority_display())

    def get_absolute_url(self):
        return reverse('incident_detail', kwargs={'pk': self.pk})

    @property
    def status(self):
        if self.resolution:
            return 'resolved'
        return 'ongoing'

    @property
    def systems_affected(self):
        if self.it_systems.exists():
            return ', '.join([i.name for i in self.it_systems.all()])
        return 'Not specified'

    @property
    def locations_affected(self):
        if self.locations.exists():
            return ', '.join([i.name for i in self.locations.all()])
        return 'All locations'

    @property
    def duration(self):
        # Returns the duration of the incident as timedelta, or None if ongoing.
        if self.resolution:
            return self.resolution - self.start
        return None

    def rto_met(self):
        # Returns True/False if the RTO time was met, or None if ongoing.
        if self.resolution:
            if self.duration.seconds <= self.RTO[self.priority]:
                return True
            else:
                return False
        return None

    @property
    def divisions_affected(self):
        if self.it_systems.exists():
            divs = set([i.division_name for i in self.it_systems.all() if i.division_name])
            return ', '.join(divs)
        return None


class IncidentLog(models.Model):
    """Represents a log entry related to a single Incident.
    """
    incident = models.ForeignKey(Incident, on_delete=models.PROTECT)
    created = models.DateTimeField(auto_now_add=True)
    log = models.TextField()

    class Meta:
        ordering = ('created',)

    def save(self, *args, **kwargs):
        """After saving a log entry, save the parent incident to set the updated field value.
        """
        super(IncidentLog, self).save(*args, **kwargs)
        self.incident.save()


class StandardChange(models.Model):
    """A standard change that will be used multiple times.
    """
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=256)
    description = models.TextField(blank=True, null=True)
    implementation = models.TextField(null=True, blank=True, help_text='Implementation/deployment instructions')
    implementation_docs = models.FileField(
        null=True, blank=True, upload_to='uploads/%Y/%m/%d', help_text='Implementation/deployment instructions (attachment)')
    it_systems = models.ManyToManyField(
        ITSystem, blank=True, verbose_name='IT Systems', help_text='IT System(s) affected by the standard change')
    approver = models.ForeignKey(DepartmentUser, on_delete=models.PROTECT)
    expiry = models.DateField(null=True, blank=True)

    def __str__(self):
        return '{}: {}'.format(self.pk, smart_truncate(self.name))


class ChangeRequest(models.Model):
    """A model for change requests. Will be linked to API to allow application of a change request.
    """
    CHANGE_TYPE_CHOICES = (
        (0, "Normal"),
        (1, "Standard"),
        (2, "Emergency"),
    )
    STATUS_CHOICES = (
        (0, "Draft"),  # Not yet approved or submitted to CAB.
        (1, "Submitted for endorsement"),  # Submitted for endorsement by approver, not yet ready for CAB assessment.
        (2, "Scheduled for CAB"),  # Approved and ready to be assessed at CAB.
        (3, "Ready"),  # Approved at CAB, ready to be undertaken.
        (4, "Complete"),  # Undertaken and completed.
        (5, "Rolled back"),  # Undertaken and rolled back.
        (6, "Cancelled"),
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    title = models.CharField(max_length=255, help_text='A short summary title for this change')
    change_type = models.SmallIntegerField(
        choices=CHANGE_TYPE_CHOICES, default=0, db_index=True, help_text='The change type')
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0, db_index=True)
    standard_change = models.ForeignKey(
        StandardChange, on_delete=models.PROTECT, null=True, blank=True,
        help_text='Standard change reference (if applicable)')
    requester = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, related_name='requester', null=True, blank=True,
        help_text='The person who is requesting this change')
    approver = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, related_name='approver', null=True, blank=True,
        help_text='The person who will endorse this change prior to CAB')
    implementer = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, related_name='implementer', blank=True, null=True,
        help_text='The person who will implement this change')
    description = models.TextField(
        null=True, blank=True, help_text='A brief description of what the change is for and why it is being undertaken')
    incident_url = models.URLField(
        max_length=2048, null=True, blank=True, verbose_name='Incident URL',
        help_text='If the change is to address an incident, URL to the incident details')
    test_date = models.DateField(null=True, blank=True, help_text='Date on which the change was tested')
    planned_start = models.DateTimeField(null=True, blank=True, help_text='Time that the change is planned to begin')
    planned_end = models.DateTimeField(null=True, blank=True, help_text='Time that the change is planned to end')
    completed = models.DateTimeField(null=True, blank=True, help_text='Time that the change was completed')
    it_systems = models.ManyToManyField(
        ITSystem, blank=True, verbose_name='IT Systems', help_text='IT System(s) affected by the change')
    implementation = models.TextField(null=True, blank=True, help_text='Implementation/deployment instructions')
    implementation_docs = models.FileField(
        null=True, blank=True, upload_to='uploads/%Y/%m/%d', help_text='Implementation/deployment instructions (attachment)')
    outage = models.DurationField(
        null=True, blank=True, help_text='Duration of outage required to complete the change (hh:mm:ss).')
    communication = models.TextField(
        null=True, blank=True, help_text='Description of all communications to be undertaken')
    broadcast = models.FileField(
        null=True, blank=True, upload_to='uploads/%Y/%m/%d',
        help_text='The broadcast text to be emailed to users regarding this change')
    unexpected_issues = models.BooleanField(default=False, help_text='Unexpected/unplanned issues were encountered during the change')
    notes = models.TextField(null=True, blank=True, help_text='Details of any unexpected issues, observations, etc.')

    def __str__(self):
        return '{}: {}'.format(self.pk, smart_truncate(self.title))

    class Meta:
        ordering = ('-planned_start',)

    @property
    def is_standard_change(self):
        return self.change_type == 1

    @property
    def is_draft(self):
        return self.status == 0

    @property
    def is_submitted(self):
        return self.status == 1

    @property
    def is_scheduled(self):
        return self.status == 2

    @property
    def is_ready(self):
        return self.status == 3

    @property
    def systems_affected(self):
        if self.it_systems.exists():
            return ', '.join([i.name for i in self.it_systems.all()])
        return 'Not specified'

    @property
    def implementation_docs_filename(self):
        return path.basename(self.implementation_docs.name)

    @property
    def broadcast_filename(self):
        return path.basename(self.broadcast.name)

    def get_absolute_url(self):
        return reverse('change_request_detail', kwargs={'pk': self.pk})

    def email_approver(self, request=None):
        # Send an email to the approver (if defined) with a link to the change request endorse view.
        if not self.approver:
            return None
        subject = 'Approval for change request {}'.format(self)
        if request:
            endorse_url = request.build_absolute_uri(reverse('change_request_endorse', kwargs={'pk': self.pk}))
        else:
            domain = Site.objects.get_current().domain
            endorse_url = '{}{}'.format(domain, reverse('change_request_endorse', kwargs={'pk': self.pk}))
        text_content = """This is an automated message to let you know that you have
            been assigned as the approver for a change request submitted to OIM by {}.\n
            Please visit the following URL, review the change request details and register
            endorsement or rejection of the change:\n
            {}\n
            """.format(self.requester.get_full_name(), endorse_url)
        html_content = """<p>This is an automated message to let you know that you have
            been assigned as the approver for a change request submitted to OIM by {0}.</p>
            <p>Please visit the following URL, review the change request details and register
            endorsement or rejection of the change:</p>
            <ul><li><a href="{1}">{1}</a></li></ul>
            """.format(self.requester.get_full_name(), endorse_url)
        msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, [self.approver.email])
        msg.attach_alternative(html_content, 'text/html')
        msg.send()

    def email_implementer(self, request=None):
        # Send an email to the implementer (if defined) with a link to the change request endorse view.
        if not self.implementer:
            return None
        subject = 'Completion of change request {}'.format(self)
        if request:
            complete_url = request.build_absolute_uri(reverse('change_request_complete', kwargs={'pk': self.pk}))
        else:
            domain = Site.objects.get_current().domain
            complete_url = '{}{}'.format(domain, reverse('change_request_complete', kwargs={'pk': self.pk}))
        text_content = """This is an automated message to let you know that you are recorded as the
            implementer for change request {}, scheduled to be undertaken on {}.\n
            Please visit the following URL and record the outcome of the change in order to finalise it:\n
            {}\n
            """.format(self, self.planned_start.strftime('%d/%b/%Y at %H:%M'), complete_url)
        html_content = """<p>This is an automated message to let you know that you are recorded as the
            implementer for change request {0}, scheduled to be undertaken on {1}.</p>
            <p>Please visit the following URL and record the outcome of the change in order to finalise it:</p>
            <ul><li><a href="{2}">{2}</a></li></ul>
            """.format(self, self.planned_start.strftime('%d/%b/%Y at %H:%M'), complete_url)
        msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, [self.implementer.email])
        msg.attach_alternative(html_content, 'text/html')
        msg.send()


class ChangeLog(models.Model):
    """Represents a log entry related to a single Change Request.
    """
    change_request = models.ForeignKey(ChangeRequest, on_delete=models.PROTECT)
    created = models.DateTimeField(auto_now_add=True)
    log = models.TextField()

    class Meta:
        ordering = ('created',)

    def save(self, *args, **kwargs):
        """After saving a log entry, save the parent change to set the updated field value.
        """
        super(ChangeLog, self).save(*args, **kwargs)
        self.change_request.save()
