from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import JSONField, ArrayField
from django.contrib.gis.db import models
from django.utils import timezone
from django.utils.html import format_html
from json2html import json2html
from mptt.models import MPTTModel, TreeForeignKey


class DepartmentUser(MPTTModel):
    """Represents a Department user. Maps to an object managed by Active Directory.
    """
    ACTIVE_FILTER = {'active': True, 'email__isnull': False, 'cost_centre__isnull': False, 'contractor': False}
    # The following choices are intended to match options in Alesco.
    ACCOUNT_TYPE_CHOICES = (
        (2, 'L1 User Account - Permanent'),
        (3, 'L1 User Account - Agency contract'),
        (0, 'L1 User Account - Department fixed-term contract'),
        (8, 'L1 User Account - Seasonal'),
        (6, 'L1 User Account - Vendor'),
        (7, 'L1 User Account - Volunteer'),
        (1, 'L1 User Account - Other/Alumni'),
        (11, 'L1 User Account - RoomMailbox'),
        (12, 'L1 User Account - EquipmentMailbox'),
        (10, 'L2 Service Account - System'),
        (5, 'L1 Group (shared) Mailbox - Shared account'),
        (9, 'L1 Role Account - Role-based account'),
        (4, 'Terminated'),
        (14, 'Unknown - AD disabled'),
        (15, 'Cleanup - Permanent'),
        (16, 'Unknown - AD active'),
    )
    # The following is a list of account type of normally exclude from user queries.
    # E.g. shared accounts, meeting rooms, terminated accounts, etc.
    ACCOUNT_TYPE_EXCLUDE = [4, 5, 9, 10, 11, 12, 14, 16]
    # The following is a list of account types set for individual staff/vendors,
    # i.e. no shared or role-based account types.
    # NOTE: it may not necessarily be the inverse of the previous list.
    ACCOUNT_TYPE_USER = [2, 3, 0, 8, 6, 7, 1]
    POSITION_TYPE_CHOICES = (
        (0, 'Full time'),
        (1, 'Part time'),
        (2, 'Casual'),
        (3, 'Other'),
    )

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    # Fields directly related to the employee, which map to a field in Azure Active Directory.
    # The Azure AD field name is listed after each field.
    azure_guid = models.CharField(
        max_length=48, unique=True, null=True, blank=True, verbose_name='Azure GUID',
        editable=False, help_text='Azure AD ObjectId')  # ObjectId
    active = models.BooleanField(
        default=True, editable=False, help_text='Account is enabled/disabled within Active Directory.')  # AccountEnabled
    email = models.EmailField(unique=True, editable=False, help_text='Account primary email address')  # Mail
    name = models.CharField(
        max_length=128, verbose_name='display name', help_text='Format: [Given name] [Surname]')  # DisplayName
    given_name = models.CharField(
        max_length=128, null=True, blank=True,
        help_text='Legal first name (matches birth certificate/passport/etc.)')  # GivenName
    surname = models.CharField(
        max_length=128, null=True, blank=True,
        help_text='Legal surname (matches birth certificate/passport/etc.)')  # Surname
    title = models.CharField(
        max_length=128, null=True, blank=True,
        help_text='Occupation position title (should match Alesco)')  # JobTitle
    telephone = models.CharField(
        max_length=128, null=True, blank=True, help_text='Work telephone number')  # TelephoneNumber
    mobile_phone = models.CharField(
        max_length=128, null=True, blank=True, help_text='Work mobile number')  # Mobile
    manager = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='manages', help_text='Staff member who manages this employee')  # Manager
    cost_centre = models.ForeignKey(
        'organisation.CostCentre', on_delete=models.PROTECT, null=True, blank=True,
        help_text='Cost centre to which the employee currently belongs')  # CompanyName
    location = models.ForeignKey(
        'Location', on_delete=models.PROTECT, null=True, blank=True,
        help_text='Current physical workplace.')  # PhysicalDeliveryOfficeName, StreetAddress
    proxy_addresses = ArrayField(base_field=models.CharField(
        max_length=254, blank=True), blank=True, null=True, help_text='Email aliases')  # ProxyAddresses
    assigned_licences = ArrayField(base_field=models.CharField(
        max_length=254, blank=True), blank=True, null=True, help_text='Assigned Office 365 licences')  # AssignedLicenses
    mail_nickname = models.CharField(max_length=128, null=True, blank=True)  # MailNickName
    dir_sync_enabled = models.NullBooleanField(default=None)  # DirSyncEnabled

    # Metadata fields with no direct equivalent in AD.
    # They are used for internal reporting and the address book.
    preferred_name = models.CharField(
        max_length=256, null=True, blank=True, help_text='Employee-editable preferred name.')
    extension = models.CharField(
        max_length=128, null=True, blank=True, verbose_name='VoIP extension')
    home_phone = models.CharField(max_length=128, null=True, blank=True)
    other_phone = models.CharField(max_length=128, null=True, blank=True)
    position_type = models.PositiveSmallIntegerField(
        choices=POSITION_TYPE_CHOICES, null=True, blank=True, default=0,
        help_text='Employee position working arrangement (should match Alesco status)')
    employee_id = models.CharField(
        max_length=128, null=True, unique=True, blank=True, verbose_name='Employee ID',
        help_text='HR Employee ID.')
    name_update_reference = models.CharField(
        max_length=512, null=True, blank=True, verbose_name='update reference',
        help_text='Reference for name/CC change request')
    vip = models.BooleanField(
        default=False,
        help_text="An individual who carries out a critical role for the department")
    executive = models.BooleanField(
        default=False, help_text="An individual who is an executive")
    contractor = models.BooleanField(
        default=False,
        help_text="An individual who is an external contractor (does not include agency contract staff)")
    notes = models.TextField(
        null=True, blank=True,
        help_text='Records relevant to any AD account extension, expiry or deletion (e.g. ticket #).')
    working_hours = models.TextField(
        default="N/A", null=True, blank=True,
        help_text="Description of normal working hours")
    account_type = models.PositiveSmallIntegerField(
        choices=ACCOUNT_TYPE_CHOICES, null=True, blank=True,
        help_text='Employee network account status (should match Alesco status)')
    security_clearance = models.BooleanField(
        default=False, verbose_name='security clearance granted',
        help_text='''Security clearance approved by CC Manager (confidentiality
        agreement, referee check, police clearance, etc.''')

    # Fields below are likely to be deprecated and progressively removed.
    username = models.CharField(
        max_length=128, editable=False, blank=True, null=True, help_text='Pre-Windows 2000 login username.')
    shared_account = models.BooleanField(
        default=False, editable=False, help_text='Automatically set from account type.')
    org_unit = models.ForeignKey(
        'organisation.OrgUnit', on_delete=models.PROTECT, null=True, blank=True,
        verbose_name='organisational unit',
        help_text="""The organisational unit that represents the user's"""
        """ primary physical location (also set their distribution group).""")
    ad_guid = models.CharField(
        max_length=48, unique=True, null=True, blank=True, verbose_name='AD GUID',
        help_text='Locally stored AD GUID. This field must match GUID in the AD object for sync to be successful')
    # NOTE: remove parent field after copying data to manager.
    parent = TreeForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='children', editable=True, verbose_name='Reports to',
        help_text='Person that this employee reports to')
    cost_centres_secondary = models.ManyToManyField(
        'organisation.CostCentre', related_name='cost_centres_secondary', editable=False,
        blank=True, help_text='NOTE: this provides security group access (e.g. T drives).')
    org_units_secondary = models.ManyToManyField(
        'organisation.OrgUnit', related_name='org_units_secondary', blank=True, editable=False,
        help_text='NOTE: this provides email distribution group access.')
    org_data = JSONField(null=True, blank=True, editable=False)
    secondary_locations = models.ManyToManyField(
        "organisation.Location", blank=True, related_name='departmentuser_secondary',
        help_text="Only to be used for staff working in additional loactions from their cost centre")
    expiry_date = models.DateTimeField(
        null=True, blank=True, help_text='Date that the AD account will expire.')
    date_hr_term = models.DateTimeField(
        null=True, blank=True, editable=False, verbose_name='HR termination date',
        help_text='Date on file with HR as the job termination date.')
    hr_auto_expiry = models.BooleanField(
        default=False, verbose_name='HR auto expiry',
        help_text='When the HR termination date changes, automatically update the expiry date to match.')
    alesco_data = JSONField(
        null=True, blank=True, help_text='Readonly data from Alesco')
    o365_licence = models.NullBooleanField(
        default=None, editable=False,
        help_text='Account consumes an Office 365 licence.')
    extra_data = JSONField(null=True, blank=True)

    class MPTTMeta:
        order_insertion_by = ['name']

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        """Override the save method with additional business logic.
        """
        if self.employee_id:
            if (self.employee_id.lower() == "n/a") or (self.employee_id.strip() == ''):
                self.employee_id = None
        '''
        # If the CC is set but not the OrgUnit, use the CC's OrgUnit.
        if self.cost_centre and not self.org_unit:
            self.org_unit = self.cost_centre.org_position
        if self.cost_centre and self.org_unit:
            self.org_data = self.org_data or {}
            self.org_data["units"] = list(self.org_unit.get_ancestors(include_self=True).values(
                "id", "name", "acronym", "unit_type", "costcentre__code",
                "costcentre__name", "location__name"))
            self.org_data["unit"] = self.org_data["units"][-1] if len(self.org_data["units"]) else None
            if self.org_unit.location:
                self.org_data["location"] = self.org_unit.location.as_dict()
            for unit in self.org_data["units"]:
                unit["unit_type"] = self.org_unit.TYPE_CHOICES_DICT[
                    unit["unit_type"]]
            if self.cost_centre:
                self.org_data["cost_centre"] = {
                    "name": self.cost_centre.org_position.name if self.cost_centre.org_position else '',
                    "code": self.cost_centre.code,
                    "cost_centre_manager": str(self.cost_centre.manager),
                    "business_manager": str(self.cost_centre.business_manager),
                    "admin": str(self.cost_centre.admin),
                    "tech_contact": str(self.cost_centre.tech_contact),
                }
            if self.cost_centres_secondary.exists():
                self.org_data['cost_centres_secondary'] = [{
                    'name': i.name,
                    'code': i.code,
                } for i in self.cost_centres_secondary.all()]
            if self.org_units_secondary:
                self.org_data['org_units_secondary'] = [{
                    'name': i.name,
                    'acronym': i.name,
                    'unit_type': i.get_unit_type_display(),
                } for i in self.org_units_secondary.all()]
        '''
        if self.account_type in [5, 9]:  # Shared/role-based account types.
            self.shared_account = True
        super(DepartmentUser, self).save(*args, **kwargs)

    def org_data_pretty(self):
        if not self.org_data:
            return self.org_data
        return format_html(json2html.convert(json=self.org_data))

    def alesco_data_pretty(self):
        if not self.alesco_data:
            return self.alesco_data
        return format_html(json2html.convert(json=self.alesco_data, clubbing=False))

    @property
    def password_age_days(self):
        return None

    @property
    def ad_expired(self):
        if self.expiry_date and self.expiry_date < timezone.now():
            return True
        return False

    @property
    def children_filtered(self):
        return self.children.filter(**self.ACTIVE_FILTER).exclude(account_type__in=self.ACCOUNT_TYPE_EXCLUDE)

    @property
    def children_filtered_ids(self):
        return self.children_filtered.values_list('id', flat=True)

    @property
    def org_unit_chain(self):
        return self.org_unit.get_ancestors(ascending=True, include_self=True).values_list('id', flat=True)

    @property
    def group_unit(self):
        """Return the group-level org unit, as seen in the primary address book view.
        """
        if self.org_unit is not None:
            for org in self.org_unit.get_ancestors(ascending=True):
                if org.unit_type in (0, 1):
                    return org
        return self.org_unit

    def get_gal_department(self):
        """Return a string to place into the "Department" field for the Global Address List.
        """
        s = ''
        unit = self.group_unit
        if unit:
            s = '{}'.format(unit.name)
        return s

    def get_full_name(self):
        # Return given_name and surname, with a space in between.
        full_name = '{} {}'.format(self.given_name, self.surname)
        return full_name.strip()

    def generate_ad_actions(self, azure_user):
        """For given Azure AD user and DepartmentUser objects, generate ADAction objects
        that specify the changes which need to be carried out in order to synchronise AD
        with IT Assets.
        ``azure_user`` will be a dict object derived from current Azure AD JSON output.
        """
        if not self.azure_guid:
            return []

        actions = []

        for field in [
            # ('AccountEnabled', 'active'),
            # ('Mail', 'email'),
            ('DisplayName', 'name'),
            ('GivenName', 'given_name'),
            ('Surname', 'surname'),
            ('JobTitle', 'title'),
            ('TelephoneNumber', 'telephone'),
            ('Mobile', 'mobile_phone'),
            #'Manager',
            #CompanyName, Department
            #PhysicalDeliveryOfficeName, PostalCode, State, StreetAddress
            # ('ProxyAddresses', 'proxy_addresses'),
        ]:
            if azure_user[field[0]] != getattr(self, field[1]):
                # Get/create a non-completed ADAction for this dept user, for these fields.
                # This should mean that only one ADAction object is generated for a given field,
                # even if the value it IT Assets changes more than once before being synced in AD.
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field=field[0],
                    field=field[1],
                    completed=None,
                )
                action.ad_field_value = azure_user[field[0]]
                action.field_value = getattr(self, field[1])
                action.save()
                actions.append(action)

        return actions

    def audit_ad_actions(self, azure_user):
        """For given Azure AD user and DepartmentUser objects, check any incomplete ADAction
        objects that specify changes to be made for the AD user. If the ADAction is no longer
        required (e.g. changes have been completed/reverted), delete the ADAction object.
        ``azure_user`` will be a dict object derived from current Azure AD JSON output.
        """
        actions = ADAction.objects.filter(department_user=self, completed__isnull=True)

        for action in actions:
            if getattr(self, action.field) == azure_user[action.ad_field]:
                action.delete()


ACTION_TYPE_CHOICES = (
    ('Change email', 'Change email'),  # Separate from 'change field' because this is a significant operation.
    ('Change account field', 'Change account field'),
    ('Disable account', 'Disable account'),
    ('Enable account', 'Enable account'),
)


class ADAction(models.Model):
    """Represents a single "action" or change that needs to be carried out to the Active Directory
    object which matches a DepartmentUser object.
    """
    created = models.DateTimeField(auto_now_add=True)
    department_user = models.ForeignKey(DepartmentUser, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=128, choices=ACTION_TYPE_CHOICES)
    ad_field = models.CharField(max_length=128, blank=True, null=True, help_text='Name of the field in Active Directory')
    ad_field_value = models.TextField(blank=True, null=True, help_text='Value of the field in Active Directory')
    field = models.CharField(max_length=128, blank=True, null=True, help_text='Name of the field in IT Assets')
    field_value = models.TextField(blank=True, null=True, help_text='Value of the field in IT Assets')
    completed = models.DateTimeField(null=True, blank=True, editable=False)
    completed_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True, editable=False)
    # log = models.TextField()
    # automated = models.BooleanField(default=False, help_text='Will this action be completed by automated processes?')

    class Meta:
        verbose_name = 'AD action'
        verbose_name_plural = 'AD actions'

    def __str__(self):
        return '{}: {} ({} -> {})'.format(
            self.department_user.azure_guid, self.action_type, self.ad_field, self.field_value
        )


class Location(models.Model):
    """A model to represent a physical location.
    """
    name = models.CharField(max_length=256, unique=True)
    manager = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, null=True, blank=True,
        related_name='location_manager')
    address = models.TextField(unique=True, blank=True)
    pobox = models.TextField(blank=True, verbose_name='PO Box')
    phone = models.CharField(max_length=128, null=True, blank=True)
    fax = models.CharField(max_length=128, null=True, blank=True)
    email = models.CharField(max_length=128, null=True, blank=True)
    point = models.PointField(null=True, blank=True)
    url = models.CharField(
        max_length=2000,
        help_text='URL to webpage with more information',
        null=True,
        blank=True)
    bandwidth_url = models.CharField(
        max_length=2000,
        help_text='URL to prtg graph of bw utilisation',
        null=True,
        blank=True)
    ascender_code = models.CharField(max_length=16, null=True, blank=True, unique=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def as_dict(self):
        return {k: getattr(self, k) for k in (
            'id', 'name', 'address', 'pobox', 'phone', 'fax', 'email') if getattr(self, k)}


class OrgUnit(MPTTModel):
    """Represents an element within the Department organisational hierarchy.
    """
    TYPE_CHOICES = (
        (0, 'Department (Tier one)'),
        (1, 'Division (Tier two)'),
        (11, 'Division'),
        (9, 'Group'),
        (2, 'Branch'),
        (7, 'Section'),
        (3, 'Region'),
        (6, 'District'),
        (8, 'Unit'),
        (5, 'Office'),
        (10, 'Work centre'),
    )
    TYPE_CHOICES_DICT = dict(TYPE_CHOICES)
    unit_type = models.PositiveSmallIntegerField(choices=TYPE_CHOICES)
    ad_guid = models.CharField(
        max_length=48, unique=True, null=True, editable=False)
    ad_dn = models.CharField(
        max_length=512, unique=True, null=True, editable=False)
    name = models.CharField(max_length=256)
    acronym = models.CharField(max_length=16, null=True, blank=True)
    manager = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, null=True, blank=True)
    parent = TreeForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='children', db_index=True)
    details = JSONField(null=True, blank=True)
    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, null=True, blank=True)
    sync_o365 = models.BooleanField(
        default=True, help_text='Sync this to O365 (creates a security group).')
    active = models.BooleanField(default=True)

    class MPTTMeta:
        order_insertion_by = ['name']

    class Meta:
        ordering = ('name',)

    def cc(self):
        return ', '.join([str(x) for x in self.costcentre_set.all()])

    def __str__(self):
        return self.name

    def members(self):
        return DepartmentUser.objects.filter(org_unit__in=self.get_descendants(
            include_self=True), **DepartmentUser.ACTIVE_FILTER)

    def children_active(self):
        return self.children.filter(active=True)

    def get_descendants_active(self, *args, **kwargs):
        """Exclude 'inactive' OrgUnit objects from get_descendants() queryset.
        Returns a list of OrgUnits.
        """
        descendants = self.get_descendants(*args, **kwargs).exclude(active=False)
        return descendants


DIVISION_CHOICES = (
    ("BCS", "DBCA Biodiversity and Conservation Science"),
    ("BGPA", "Botanic Gardens and Parks Authority"),
    ("CBS", "DBCA Corporate and Business Services"),
    ("CPC", "Conservation and Parks Commission"),
    ("ODG", "Office of the Director General"),
    ("PWS", "Parks and Wildlife Service"),
    ("RIA", "Rottnest Island Authority"),
    ("ZPA", "Zoological Parks Authority"),
)
#{'BCS', 'BGPA', 'CBS', 'CPC', 'ODG', 'PWS', 'RIA', 'ZPA'}


class CostCentre(models.Model):
    """Models the details of a Department cost centre / chart of accounts.
    """
    name = models.CharField(max_length=128, unique=True, editable=False)
    code = models.CharField(max_length=16, unique=True)
    chart_acct_name = models.CharField(
        max_length=256, blank=True, null=True, verbose_name='chart of accounts name')
    # NOTE: delete division field after copying data to division_name.
    division = models.ForeignKey(
        OrgUnit, on_delete=models.PROTECT, null=True, editable=False, related_name='costcentres_in_division')
    division_name = models.CharField(max_length=128, choices=DIVISION_CHOICES, null=True, blank=True)
    org_position = models.ForeignKey(
        OrgUnit, on_delete=models.PROTECT, blank=True, null=True)
    manager = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, related_name='manage_ccs',
        null=True, blank=True)
    business_manager = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, related_name='bmanage_ccs',
        help_text='Business Manager', null=True, blank=True)
    admin = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, related_name='admin_ccs',
        help_text='Adminstration Officer', null=True, blank=True)
    tech_contact = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, related_name='tech_ccs',
        help_text='Technical Contact', null=True, blank=True)
    ascender_code = models.CharField(max_length=16, null=True, blank=True, unique=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ('code',)

    def __str__(self):
        return self.code

    def get_division(self):
        if not self.org_position:
            return None
        return self.org_position.get_ancestors(include_self=True).filter(unit_type=1).first()


class CommonFields(models.Model):
    """Meta model class used by other apps
    """
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    org_unit = models.ForeignKey(OrgUnit, on_delete=models.PROTECT, null=True, blank=True)
    cost_centre = models.ForeignKey(CostCentre, on_delete=models.PROTECT, null=True, blank=True)
    extra_data = JSONField(null=True, blank=True)

    def extra_data_pretty(self):
        if not self.extra_data:
            return self.extra_data
        try:
            return format_html(json2html.convert(json=self.extra_data))
        except Exception as e:
            return repr(e)

    class Meta:
        abstract = True
