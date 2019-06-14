from datetime import datetime
from django.contrib.postgres.fields import JSONField
from django.contrib.gis.db import models
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from io import BytesIO
from json2html import json2html
from mptt.models import MPTTModel, TreeForeignKey
from PIL import Image
import os

from organisation.utils import get_photo_path, get_photo_ad_path, convert_ad_timestamp


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
    cost_centre = models.ForeignKey('organisation.CostCentre', on_delete=models.PROTECT, null=True)
    cost_centres_secondary = models.ManyToManyField(
        'organisation.CostCentre', related_name='cost_centres_secondary', editable=False,
        blank=True, help_text='NOTE: this provides security group access (e.g. T drives).')
    org_unit = models.ForeignKey(
        'organisation.OrgUnit', on_delete=models.PROTECT, null=True, blank=True,
        verbose_name='organisational unit',
        help_text="""The organisational unit that represents the user's"""
        """ primary physical location (also set their distribution group).""")
    org_units_secondary = models.ManyToManyField(
        'organisation.OrgUnit', related_name='org_units_secondary', blank=True, editable=False,
        help_text='NOTE: this provides email distribution group access.')
    extra_data = JSONField(null=True, blank=True)
    ad_guid = models.CharField(
        max_length=48, unique=True, null=True, blank=True, verbose_name='AD GUID',
        help_text='Locally stored AD GUID. This field must match GUID in the AD object for sync to be successful')
    azure_guid = models.CharField(
        max_length=48, unique=True, null=True, blank=True, verbose_name='Azure GUID',
        help_text='Azure AD GUID.')
    ad_dn = models.CharField(
        max_length=512, unique=True, null=True, blank=True, verbose_name='AD DN',
        help_text='AD DistinguishedName value.')
    ad_data = JSONField(null=True, blank=True, editable=False)
    org_data = JSONField(null=True, blank=True, editable=False)
    employee_id = models.CharField(
        max_length=128, null=True, unique=True, blank=True, verbose_name='Employee ID',
        help_text='HR Employee ID.')
    email = models.EmailField(unique=True)
    username = models.CharField(
        max_length=128, editable=False, blank=True, null=True,
        help_text='Pre-Windows 2000 login username.')
    name = models.CharField(max_length=128, db_index=True, help_text='Format: [Given name] [Surname]')
    given_name = models.CharField(
        max_length=128, null=True,
        help_text='Legal first name (matches birth certificate/password/etc.)')
    surname = models.CharField(
        max_length=128, null=True,
        help_text='Legal surname (matches birth certificate/password/etc.)')
    name_update_reference = models.CharField(
        max_length=512, null=True, blank=True, verbose_name='update reference',
        help_text='Reference for name/CC change request')
    preferred_name = models.CharField(
        max_length=256, null=True, blank=True, help_text='Employee-editable preferred name.')
    title = models.CharField(
        max_length=128, null=True,
        help_text='Occupation position title (should match Alesco)')
    position_type = models.PositiveSmallIntegerField(
        choices=POSITION_TYPE_CHOICES, null=True, blank=True, default=0,
        help_text='Employee position working arrangement (should match Alesco status)')
    parent = TreeForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='children', editable=True, verbose_name='Reports to',
        help_text='Person that this employee reports to')
    expiry_date = models.DateTimeField(
        null=True, blank=True, help_text='Date that the AD account will expire.')
    date_hr_term = models.DateTimeField(
        null=True, blank=True, editable=False, verbose_name='HR termination date', help_text='Date on file with HR as the job termination date.')
    hr_auto_expiry = models.BooleanField(
        default=False, verbose_name='HR auto expiry', help_text='When the HR termination date changes, automatically update the expiry date to match.')
    date_ad_updated = models.DateTimeField(
        null=True, editable=False, verbose_name='Date AD updated',
        help_text='The date when the AD account was last updated.')
    location = models.ForeignKey(
        'Location', on_delete=models.PROTECT, null=True, blank=True,
        help_text='Current place of work.')
    telephone = models.CharField(max_length=128, null=True, blank=True)
    mobile_phone = models.CharField(max_length=128, null=True, blank=True)
    extension = models.CharField(
        max_length=128, null=True, blank=True, verbose_name='VoIP extension')
    home_phone = models.CharField(max_length=128, null=True, blank=True)
    other_phone = models.CharField(max_length=128, null=True, blank=True)
    active = models.BooleanField(
        default=True, editable=False,
        help_text='Account is active within Active Directory.')
    ad_deleted = models.BooleanField(
        default=False, editable=False, verbose_name='AD deleted',
        help_text='Account has been deleted in Active Directory.')
    in_sync = models.BooleanField(
        default=False, editable=False,
        help_text='CMS data has been synchronised from AD data.')
    vip = models.BooleanField(
        default=False,
        help_text="An individual who carries out a critical role for the department")
    executive = models.BooleanField(
        default=False, help_text="An individual who is an executive")
    contractor = models.BooleanField(
        default=False,
        help_text="An individual who is an external contractor (does not include agency contract staff)")
    photo = models.ImageField(blank=True, upload_to=get_photo_path)
    photo_ad = models.ImageField(
        blank=True, editable=False, upload_to=get_photo_ad_path)
    sso_roles = models.TextField(
        null=True, editable=False, help_text="Groups/roles separated by semicolon")
    notes = models.TextField(
        null=True, blank=True,
        help_text='Records relevant to any AD account extension, expiry or deletion (e.g. ticket #).')
    working_hours = models.TextField(
        default="N/A", null=True, blank=True,
        help_text="Description of normal working hours")
    secondary_locations = models.ManyToManyField("organisation.Location", blank=True,
        related_name='departmentuser_secondary',
        help_text="Only to be used for staff working in additional loactions from their cost centre")
    populate_primary_group = models.BooleanField(
        default=True,
        help_text="If unchecked, user will not be added to primary group email")
    account_type = models.PositiveSmallIntegerField(
        choices=ACCOUNT_TYPE_CHOICES, null=True, blank=True,
        help_text='Employee account status (should match Alesco status)')
    alesco_data = JSONField(
        null=True, blank=True, help_text='Readonly data from Alesco')
    security_clearance = models.BooleanField(
        default=False, verbose_name='security clearance granted',
        help_text='''Security clearance approved by CC Manager (confidentiality
        agreement, referee check, police clearance, etc.''')
    o365_licence = models.NullBooleanField(
        default=None, editable=False,
        help_text='Account consumes an Office 365 licence.')
    shared_account = models.BooleanField(
        default=False, editable=False,
        help_text='Automatically set from account type.')

    class MPTTMeta:
        order_insertion_by = ['name']

    def __init__(self, *args, **kwargs):
        super(DepartmentUser, self).__init__(*args, **kwargs)
        # Store the pre-save values of some fields on object init.
        self.__original_given_name = self.given_name
        self.__original_surname = self.surname
        self.__original_employee_id = self.employee_id
        self.__original_cost_centre_id = self.cost_centre_id
        self.__original_name = self.name
        self.__original_org_unit_id = self.org_unit_id
        self.__original_expiry_date = self.expiry_date
        self.__original_photo = self.photo

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        """Override the save method with additional business logic.
        """
        if self.employee_id:
            if (self.employee_id.lower() == "n/a") or (self.employee_id.strip() == ''):
                self.employee_id = None
        self.in_sync = True if self.date_ad_updated else False
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

        if self.account_type in [5, 9]:  # Shared/role-based account types.
            self.shared_account = True
        super(DepartmentUser, self).save(*args, **kwargs)

    def update_photo_ad(self):
        # If the photo is set to blank, clear any AD thumbnail.
        if not self.photo:
            if self.photo_ad:
                self.photo_ad.delete()
            return
        else:
            # Account for missing media files.
            try:
                self.photo.file
            except FileNotFoundError:
                return

        # Update self.photo_ad to a 240x240 thumbnail >10 kb in size.
        if hasattr(self.photo.file, 'content_type'):
            PHOTO_TYPE = self.photo.file.content_type
            if PHOTO_TYPE == 'image/jpeg':
                PIL_TYPE = 'jpeg'
            elif PHOTO_TYPE == 'image/png':
                PIL_TYPE = 'png'
            else:
                return
        else:
            PIL_TYPE = 'jpeg'

        # Good defaults to get ~10kb JPEG images
        PHOTO_AD_SIZE = (240, 240)
        PIL_QUALITY = 75
        # Remote file size limit
        PHOTO_AD_FILESIZE = 10000
        image = Image.open(BytesIO(self.photo.read()))
        image.thumbnail(PHOTO_AD_SIZE, Image.LANCZOS)

        # In case we miss 10kb, drop the quality and recompress
        for i in range(12):
            temp_buffer = BytesIO()
            image.convert('RGB').save(temp_buffer, PIL_TYPE, quality=PIL_QUALITY, optimize=True)
            length = temp_buffer.tell()
            if length <= PHOTO_AD_FILESIZE:
                break
            if PIL_TYPE == 'png':
                PIL_TYPE = 'jpeg'
            else:
                PIL_QUALITY -= 5

        temp_buffer.seek(0)
        self.photo_ad.save(os.path.basename(self.photo.name),
                           ContentFile(temp_buffer.read()), save=False)

    def org_data_pretty(self):
        if not self.org_data:
            return self.org_data
        return format_html(json2html.convert(json=self.org_data))

    def ad_data_pretty(self):
        if not self.ad_data:
            return self.ad_data
        return format_html(json2html.convert(json=self.ad_data))

    def alesco_data_pretty(self):
        if not self.alesco_data:
            return self.alesco_data
        return format_html(json2html.convert(json=self.alesco_data, clubbing=False))

    @property
    def password_age_days(self):
        if self.ad_data and 'pwdLastSet' in self.ad_data:
            try:
                td = datetime.now() - convert_ad_timestamp(self.ad_data['pwdLastSet'])
                return td.days
            except:
                pass
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
        if self.org_data and 'units' in self.org_data and len(self.org_data['units']) > 0:
            s = self.org_data['units'][0]['acronym']
            if len(self.org_data['units']) > 1:
                s += ' - {}'.format(self.org_data['units'][1]['name'])
        return s

    def get_full_name(self):
        # Return given_name and surname, with a space in between.
        full_name = '{} {}'.format(self.given_name, self.surname)
        return full_name.strip()


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
        name = self.name
        if self.acronym:
            name = '{} - {}'.format(self.acronym, name)
        #if self.cc():
        #    return '{} - CC {}'.format(name, self.cc())
        return name

    def members(self):
        return DepartmentUser.objects.filter(org_unit__in=self.get_descendants(
            include_self=True), **DepartmentUser.ACTIVE_FILTER)

    def save(self, *args, **kwargs):
        self.details = self.details or {}
        self.details.update({
            'type': self.get_unit_type_display(),
        })
        super(OrgUnit, self).save(*args, **kwargs)
        if not getattr(self, 'cheap_save', False):
            for user in self.members():
                user.save()

    def children_active(self):
        return self.children.filter(active=True)

    def get_descendants_active(self, *args, **kwargs):
        """Exclude 'inactive' OrgUnit objects from get_descendants() queryset.
        Returns a list of OrgUnits.
        """
        descendants = self.get_descendants(*args, **kwargs).exclude(active=False)
        return descendants


class CostCentre(models.Model):
    """Models the details of a Department cost centre / chart of accounts.
    """
    name = models.CharField(max_length=128, unique=True, editable=False)
    code = models.CharField(max_length=16, unique=True)
    chart_acct_name = models.CharField(
        max_length=256, blank=True, null=True, verbose_name='chart of accounts name')
    division = models.ForeignKey(
        OrgUnit, on_delete=models.PROTECT, null=True, editable=False, related_name='costcentres_in_division')
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

    def save(self, *args, **kwargs):
        self.name = str(self)
        # If the CC is linked to an OrgUnit, link it to that unit's Division.
        if self.org_position:
            division = self.org_position.get_ancestors(
                include_self=True).filter(unit_type=1)
            self.division = division.first()
        else:
            self.division = None
        # Iterate through each DepartmentUser assigned to this CC to cache
        # any org stucture/CC changes on that object.
        for user in self.departmentuser_set.filter(active=True):
            user.save()
        super(CostCentre, self).save(*args, **kwargs)

    def __str__(self):
        return self.code


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

    def save(self, *args, **kwargs):
        if self.cost_centre and not self.org_unit:
            self.org_unit = self.cost_centre.org_position
        #elif self.cost_centre and self.cost_centre.org_position and self.org_unit not in self.cost_centre.org_position.get_descendants(include_self=True):
        #    self.org_unit = self.cost_centre.org_position
        super(CommonFields, self).save(*args, **kwargs)

    class Meta:
        abstract = True
