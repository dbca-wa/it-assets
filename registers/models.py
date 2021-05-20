from datetime import date
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import JSONField
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives
from django.db import models
from django.template.loader import render_to_string
from django.urls import reverse
from markdownx.utils import markdownify
from os import path
from pytz import timezone

from organisation.models import DepartmentUser, CostCentre, OrgUnit
from bigpicture.models import RiskAssessment, Dependency, Platform, RISK_CATEGORY_CHOICES
from .utils import smart_truncate

TZ = timezone(settings.TIME_ZONE)

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


class ITSystemUserGroup(models.Model):
    """A model to represent an arbitrary group of users for an IT System.
    E.g. 'All department staff', 'External govt agency staff', etc.
    """
    name = models.CharField(max_length=2048, unique=True)
    user_count = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return '{} ({})'.format(self.name, self.user_count)


class ITSystem(models.Model):
    """Represents a named system providing a package of functionality to
    Department staff (normally vendor or bespoke software), which is supported
    by OIM and/or an external vendor.
    """
    ACTIVE_FILTER = {'status__in': [0, 2]}  # Defines a queryset filter for "active" IT systems.
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
    APPLICATION_TYPE_CHOICES = (
        (1, 'Web application'),
        (2, 'Client application'),
        (3, 'Mobile application'),
        (5, 'Externally hosted application'),
        (4, 'Service'),
        (6, 'Platform'),
        (7, 'Infrastructure'),
    )
    SYSTEM_TYPE_CHOICES = (
        (1, 'Department commercial services'),
        (2, 'Department fire services'),
        (3, 'Department visitor services'),
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
        (5, 'Default'),
    )
    BACKUP_CHOICES = (
        (1, 'Point in time database with daily local'),
        (2, 'Daily local'),
        (3, 'Vendor-managed'),
    )
    DISPOSAL_ACTION_CHOICES = (
        (1, 'Retain in agency'),
        (2, 'Required as State Archive'),
        (3, 'Destroy'),
    )
    # NOTE: if the following options are updated, remember to update the get_custody_verbose method also.
    CUSTODY_CHOICES = (
        (1, 'Migrate records and maintain for the life of agency'),
        (2, 'Retain in agency, migrate records to new database or transfer to SRO when superseded'),
        (3, 'Destroy datasets when superseded, migrate records and maintain for life of agency'),
        (4, 'Retain 12 months after data migration and decommission (may retain for reference)'),
    )
    INFRASTRUCTURE_LOCATION_CHOICES = (
        (1, 'On premises'),
        (2, 'Azure cloud'),
        (3, 'AWS cloud'),
        (4, 'Other provider cloud'),
    )

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    system_id = models.CharField(max_length=16, unique=True, verbose_name='system ID')
    name = models.CharField(max_length=128, unique=True)
    acronym = models.CharField(max_length=16, null=True, blank=True)
    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES, default=4)
    link = models.CharField(
        max_length=2048, null=True, blank=True, help_text='URL to web application')
    description = models.TextField(blank=True)
    org_unit = models.ForeignKey(OrgUnit, on_delete=models.PROTECT, null=True, blank=True)
    cost_centre = models.ForeignKey(CostCentre, on_delete=models.PROTECT, null=True, blank=True)
    owner = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, null=True, blank=True,
        verbose_name='system owner',
        related_name='systems_owned', help_text='IT system owner')
    technology_custodian = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, null=True, blank=True,
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
    documentation = models.CharField(
        max_length=2048, null=True, blank=True, help_text='A link/URL to end-user documentation')
    technical_documentation = models.CharField(
        max_length=2048, null=True, blank=True, help_text='A link/URL to technical documentation')
    status_url = models.URLField(
        max_length=2048, null=True, blank=True, verbose_name='status URL',
        help_text='URL to status/uptime info')
    availability = models.PositiveIntegerField(
        choices=AVAILABILITY_CHOICES, null=True, blank=True,
        help_text='Expected availability for this system')
    user_groups = models.ManyToManyField(
        ITSystemUserGroup, blank=True, help_text='User group(s) that use this system')
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
    application_type = models.PositiveSmallIntegerField(
        choices=APPLICATION_TYPE_CHOICES, null=True, blank=True)
    system_type = models.PositiveSmallIntegerField(
        choices=SYSTEM_TYPE_CHOICES, null=True, blank=True)
    oim_internal_only = models.BooleanField(
        default=False, verbose_name='OIM internal only', help_text='For OIM use only')
    biller_code = models.CharField(
        max_length=64, null=True, blank=True,
        help_text='BPAY biller code for this system (must be unique).')
    retention_reference_no = models.CharField(
        max_length=256, null=True, blank=True,
        help_text='Retention/disposal reference no. in the current retention and disposal schedule')
    defunct_date = models.DateField(
        null=True, blank=True,
        help_text='Date on which the IT System first becomes a production (legacy) or decommissioned system')
    disposal_action = models.PositiveSmallIntegerField(
        choices=DISPOSAL_ACTION_CHOICES, null=True, blank=True, verbose_name='Disposal action',
        help_text='Final disposal action required once the custody period has expired')
    custody = models.PositiveSmallIntegerField(
        choices=CUSTODY_CHOICES, null=True, blank=True,
        help_text='Period the records will be retained before they are archived or destroyed')
    retention_comments = models.TextField(
        null=True, blank=True, verbose_name='comments',
        help_text='Comments/notes related to retention and disposal')
    platform = models.ForeignKey(
        Platform, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="The primary platform used to provide this IT system")
    dependencies = models.ManyToManyField(
        Dependency, blank=True, help_text="Dependencies used by this IT system")
    infrastructure_location = models.PositiveSmallIntegerField(
        choices=INFRASTRUCTURE_LOCATION_CHOICES, null=True, blank=True,
        help_text='The primary location of the infrastructure on which this system runs')
    risks = GenericRelation(RiskAssessment)
    extra_data = JSONField(null=True, blank=True)

    class Meta:
        verbose_name = 'IT System'
        ordering = ('name',)

    def __str__(self):
        return self.name

    @property
    def division_name(self):
        if self.cost_centre and self.cost_centre.division_name:
            return self.cost_centre.get_division_name_display()
        else:
            return ''

    def get_custody_verbose(self):
        """Return verbose/detailed output based upon the object custody field value.
        """
        map = {
            1: 'Retain in agency for the life of the Department and successor agencies, migrating records through successive upgrades of hardware and software.',
            2: 'Retain as a State archive within the agency. Migrate all data to successor database or transfer to the State Records Office when database is superseded.',
            3: 'Destroy electronic datasets when reference ceases, or data is superseded. Migrate records through successive upgrades of hardware and software for the life of the Department and successor agencies.',
            4: 'Retain 12 months after decommissioning is complete and all required data has been successfully migrated.  Note: Legacy data may be retained until reference ceases.',
        }
        if self.custody:
            return map[self.custody]
        else:
            return ''

    def get_detail_markdown(self, template=None):
        if not template:
            template = 'registers/itsystem.md'
        d = self.__dict__
        d['status'] = self.get_status_display()
        d['owner'] = self.owner.get_full_name() if self.owner else ''
        d['technology_custodian'] = self.technology_custodian.get_full_name() if self.technology_custodian else ''
        d['information_custodian'] = self.information_custodian.get_full_name() if self.information_custodian else ''
        if not d['system_reqs']:
            d['system_reqs'] = 'Not specified'
        if not d['documentation']:
            d['documentation'] = 'Not specified'
        if not self.bh_support:
            d['bh_support_name'] = 'Not specified'
            d['bh_support_telephone'] = ''
            d['bh_support_email'] = ''
        else:
            d['bh_support_name'] = self.bh_support.get_full_name()
            d['bh_support_telephone'] = self.bh_support.telephone
            d['bh_support_email'] = self.bh_support.email
        return render_to_string(template, d)

    def get_risks(self, category=None):
        # Return a set of unique risks associated with the IT System.
        # RiskAssessments can be associated with IT System dependencies, platform, or directly
        # with the IT System itself.
        if category:
            risks = self.risks.filter(category=category)
            for dep in self.dependencies.all():
                risks = risks | dep.risks.filter(category=category)
            if self.platform:
                for dep in self.platform.dependencies.all():
                    risks = risks | dep.risks.filter(category=category)
        else:
            risks = self.risks.all()
            for dep in self.dependencies.all():
                risks = risks | dep.risks.all()
            if self.platform:
                for dep in self.platform.dependencies.all():
                    risks = risks | dep.risks.all()
        return risks.distinct().order_by('category', '-rating')

    def get_risk_category_maxes(self):
        # Returns a dictionary of risk categories for this system, containing the 'maximum' risk
        # for each category (or None). Relies on get_risks() returning sorted results.
        risks = self.get_risks()
        return {c[0]: risks.filter(category=c[0]).first() for c in RISK_CATEGORY_CHOICES}

    def get_risk(self, category):
        # Return a single RiskAssessment object associated with this IT System, having the highest
        # rating, or else return None.
        return self.get_risks(category).first()

    def get_compute_dependencies(self):
        # Return a list of dependency content objects of category 'Compute'.
        # Used in the dependency list view.
        return [i.content_object for i in self.dependencies.filter(category='Compute')]


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
    endorser = models.ForeignKey(DepartmentUser, on_delete=models.PROTECT)
    expiry = models.DateField(null=True, blank=True)

    def __str__(self):
        return '{}: {}'.format(self.pk, smart_truncate(self.name))

    def get_absolute_url(self):
        return reverse('standard_change_detail', kwargs={'pk': self.pk})

    @property
    def systems_affected(self):
        if self.it_systems.exists():
            return ', '.join([i.name for i in self.it_systems.all()])
        return 'Not specified'


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
        (1, "Submitted for endorsement"),  # Submitted for endorsement, not yet ready for CAB assessment.
        (2, "Scheduled for CAB"),  # Approved and ready to be assessed at CAB.
        (3, "Ready for implementation"),  # Approved at CAB, ready to be undertaken.
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
    endorser = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, related_name='endorser', null=True, blank=True,
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
    test_result_docs = models.FileField(
        null=True, blank=True, upload_to='uploads/%Y/%m/%d', help_text='Test results record (attachment)')
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
    reference_url = models.URLField(
        max_length=2048, null=True, blank=True, verbose_name='reference URL', help_text='URL to external reference (discusssion, records, etc.)')
    post_complete_email_date = models.DateField(
        null=True, blank=True, help_text='Date on which the implementer was emailed about completion')
    # Tactical roadmap-related fields.
    initiative_name = models.CharField(max_length=255, null=True, blank=True, help_text='Tactical roadmap initiative name')
    initiative_no = models.CharField(max_length=255, null=True, blank=True, verbose_name='initiative no.', help_text='Tactical roadmap initiative number')
    project_no = models.CharField(max_length=255, null=True, blank=True, verbose_name='project no.', help_text='Project number (if applicable)')

    def __str__(self):
        return '{}: {}'.format(self.pk, smart_truncate(self.title))

    class Meta:
        ordering = ('-planned_start',)

    @property
    def is_normal_change(self):
        return self.change_type == 0

    @property
    def is_standard_change(self):
        return self.change_type == 1

    @property
    def is_emergency_change(self):
        return self.change_type == 2

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

    def formatted_markdown(self, field):
        """From the passed-in field, return the object field value rendered as HTML (assumes that
        the field value is Markdown-formatted text).
        """
        return markdownify(getattr(self, field))

    def get_absolute_url(self):
        return reverse('change_request_detail', kwargs={'pk': self.pk})

    def email_endorser(self):
        # Send an email to the endorser (if defined) with a link to the change request endorse view.
        if not self.endorser:
            return None
        subject = 'Endorsement for change request {}'.format(self)
        if Site.objects.filter(name='Change Requests').exists():
            domain = Site.objects.get(name='Change Requests').domain
        else:
            domain = Site.objects.get_current().domain
        # We need to append https below because this method is often called outside of a request.
        if domain.startswith('http://'):
            domain = domain.replace('http', 'https')
        if not domain.startswith('https://'):
            domain = 'https://' + domain
        endorse_url = '{}{}'.format(domain, reverse('change_request_endorse', kwargs={'pk': self.pk}))
        text_content = """This is an automated message to let you know that you have
            been assigned as the endorser for a change request submitted to OIM by {}.\n
            Please visit the following URL, review the change request details and register
            endorsement or rejection of the change:\n
            {}\n
            """.format(self.requester.get_full_name(), endorse_url)
        html_content = """<p>This is an automated message to let you know that you have
            been assigned as the endorser for a change request submitted to OIM by {0}.</p>
            <p>Please visit the following URL, review the change request details and register
            endorsement or rejection of the change:</p>
            <ul><li><a href="{1}">{1}</a></li></ul>
            """.format(self.requester.get_full_name(), endorse_url)
        msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, [self.endorser.email])
        msg.attach_alternative(html_content, 'text/html')
        msg.send()

    def email_requester(self):
        # Send an email to the requester (if defined) with a link to the change request completion view.
        if not self.requester:
            return None
        subject = 'Completion of change request {}'.format(self)
        if Site.objects.filter(name='Change Requests').exists():
            domain = Site.objects.get(name='Change Requests').domain
        else:
            domain = Site.objects.get_current().domain
        # We need to append https below because this method is often called outside of a request.
        if domain.startswith('http://'):
            domain = domain.replace('http', 'https')
        if not domain.startswith('https://'):
            domain = 'https://' + domain
        complete_url = '{}{}'.format(domain, reverse('change_request_complete', kwargs={'pk': self.pk}))
        text_content = """This is an automated message to let you know that you are recorded as the
            requester for change request {}, scheduled to be undertaken on {}.\n
            Please visit the following URL and record the outcome of the change in order to finalise it:\n
            {}\n
            """.format(self, self.planned_start.astimezone(TZ).strftime('%d/%b/%Y at %H:%M'), complete_url)
        html_content = """<p>This is an automated message to let you know that you are recorded as the
            requester for change request {0}, scheduled to be undertaken on {1}.</p>
            <p>Please visit the following URL and record the outcome of the change in order to finalise it:</p>
            <ul><li><a href="{2}">{2}</a></li></ul>
            """.format(self, self.planned_start.astimezone(TZ).strftime('%d/%b/%Y at %H:%M'), complete_url)
        msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, [self.requester.email])
        msg.attach_alternative(html_content, 'text/html')
        msg.send()
        self.post_complete_email_date = date.today()
        self.save()


class ChangeLog(models.Model):
    """Represents a log entry related to a single Change Request.
    """
    change_request = models.ForeignKey(ChangeRequest, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    log = models.TextField()

    class Meta:
        ordering = ('created',)

    def save(self, *args, **kwargs):
        """After saving a log entry, save the parent change to set the updated field value.
        """
        super(ChangeLog, self).save(*args, **kwargs)
        self.change_request.save()
