from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import JSONField, ArrayField, CIEmailField
from django.contrib.gis.db import models

from .utils import compare_values


class DepartmentUser(models.Model):
    """Represents a Department user. Maps to an object managed by Active Directory.
    """
    ACTIVE_FILTER = {'active': True, 'cost_centre__isnull': False, 'contractor': False}
    # The following choices are intended to match options in Ascender.
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
    # This dict maps the Microsoft SKU ID for user account licences to a human-readable name.
    # https://docs.microsoft.com/en-us/azure/active-directory/users-groups-roles/licensing-service-plan-reference
    MS_LICENCE_SKUS = {
        'c5928f49-12ba-48f7-ada3-0d743a3601d5': 'VISIO Online Plan 2',  # VISIOCLIENT
        '1f2f344a-700d-42c9-9427-5cea1d5d7ba6': 'STREAM',
        'b05e124f-c7cc-45a0-a6aa-8cf78c946968': 'ENTERPRISE MOBILITY + SECURITY E5',  # EMSPREMIUM
        'c7df2760-2c81-4ef7-b578-5b5392b571df': 'OFFICE 365 E5',  # ENTERPRISEPREMIUM
        '87bbbc60-4754-4998-8c88-227dca264858': 'POWERAPPS_INDIVIDUAL_USER',
        '6470687e-a428-4b7a-bef2-8a291ad947c9': 'WINDOWS_STORE',
        '6fd2c87f-b296-42f0-b197-1e91e994b900': 'OFFICE 365 E3',  # ENTERPRISEPACK
        'f30db892-07e9-47e9-837c-80727f46fd3d': 'FLOW_FREE',
        '440eaaa8-b3e0-484b-a8be-62870b9ba70a': 'PHONESYSTEM_VIRTUALUSER',
        'bc946dac-7877-4271-b2f7-99d2db13cd2c': 'FORMS_PRO',
        'dcb1a3ae-b33f-4487-846a-a640262fadf4': 'POWERAPPS_VIRAL',
        '338148b6-1b11-4102-afb9-f92b6cdc0f8d': 'DYN365_ENTERPRISE_P1_IW',
        '6070a4c8-34c6-4937-8dfb-39bbc6397a60': 'MEETING_ROOM',
        'a403ebcc-fae0-4ca2-8c8c-7a907fd6c235': 'POWER_BI_STANDARD',
        '111046dd-295b-4d6d-9724-d52ac90bd1f2': 'Microsoft Defender Advanced Threat Protection',  # WIN_DEF_ATP
        '710779e8-3d4a-4c88-adb9-386c958d1fdf': 'TEAMS_EXPLORATORY',
        'efccb6f7-5641-4e0e-bd10-b4976e1bf68e': 'ENTERPRISE MOBILITY + SECURITY E3',  # EMS
        '90d8b3f8-712e-4f7b-aa1e-62e7ae6cbe96': 'SMB_APPS',
        'fcecd1f9-a91e-488d-a918-a96cdb6ce2b0': 'AX7_USER_TRIAL',
        '093e8d14-a334-43d9-93e3-30589a8b47d0': 'RMSBASIC',
        '53818b1b-4a27-454b-8896-0dba576410e6': 'PROJECT ONLINE PROFESSIONAL',  # PROJECTPROFESSIONAL
        '18181a46-0d4e-45cd-891e-60aabd171b4e': 'OFFICE 365 E1',  # STANDARDPACK
        '06ebc4ee-1bb5-47dd-8120-11324bc54e06': 'MICROSOFT 365 E5',
        '66b55226-6b4f-492c-910c-a3b7a3c9d993': 'MICROSOFT 365 F3',
        '05e9a617-0261-4cee-bb44-138d3ef5d965': 'MICROSOFT 365 E3',
        'c1ec4a95-1f05-45b3-a911-aa3fa01094f5': 'INTUNE',
        '3e26ee1f-8a5f-4d52-aee2-b81ce45c8f40': 'AUDIO CONFERENCING',
        '57ff2da0-773e-42df-b2af-ffb7a2317929': 'MICROSOFT TEAMS',
        '0feaeb32-d00e-4d66-bd5a-43b5b83db82c': 'SKYPE FOR BUSINESS ONLINE (PLAN 2)',
        '4828c8ec-dc2e-4779-b502-87ac9ce28ab7': 'SKYPE FOR BUSINESS CLOUD PBX',
    }

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    # Fields directly related to the employee, which map to a field in Active Directory.
    active = models.BooleanField(
        default=True, editable=False, help_text='Account is enabled/disabled within Active Directory.')
    email = CIEmailField(unique=True, editable=False, help_text='Account primary email address')
    name = models.CharField(
        max_length=128, verbose_name='display name', help_text='Format: [Given name] [Surname]')
    given_name = models.CharField(
        max_length=128, null=True, blank=True,
        help_text='Legal first name (matches birth certificate/passport/etc.)')
    surname = models.CharField(
        max_length=128, null=True, blank=True,
        help_text='Legal surname (matches birth certificate/passport/etc.)')
    title = models.CharField(
        max_length=128, null=True, blank=True,
        help_text='Occupation position title (should match Ascender position title)')
    telephone = models.CharField(
        max_length=128, null=True, blank=True, help_text='Work telephone number')
    mobile_phone = models.CharField(
        max_length=128, null=True, blank=True, help_text='Work mobile number')
    manager = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        limit_choices_to={'active': True},
        related_name='manages', help_text='Staff member who manages this employee')
    cost_centre = models.ForeignKey(
        'organisation.CostCentre', on_delete=models.PROTECT, null=True, blank=True,
        limit_choices_to={'active': True},
        help_text='Cost centre to which the employee currently belongs')
    location = models.ForeignKey(
        'Location', on_delete=models.PROTECT, null=True, blank=True,
        limit_choices_to={'active': True},
        help_text='Current physical workplace.')
    proxy_addresses = ArrayField(base_field=models.CharField(
        max_length=254, blank=True), blank=True, null=True, help_text='Email aliases')
    assigned_licences = ArrayField(base_field=models.CharField(
        max_length=254, blank=True), blank=True, null=True, help_text='Assigned Office 365 licences')
    username = models.CharField(
        max_length=128, editable=False, blank=True, null=True, help_text='Pre-Windows 2000 login username.')  # SamAccountName in onprem AD

    # Metadata fields with no direct equivalent in AD.
    # They are used for internal reporting and the Address Book.
    org_unit = models.ForeignKey(
        'organisation.OrgUnit', on_delete=models.PROTECT, null=True, blank=True,
        limit_choices_to={'active': True},
        verbose_name='organisational unit',
        help_text="The organisational unit to which the employee belongs.")
    preferred_name = models.CharField(max_length=256, null=True, blank=True)
    extension = models.CharField(
        max_length=128, null=True, blank=True, verbose_name='VoIP extension')
    home_phone = models.CharField(max_length=128, null=True, blank=True)
    other_phone = models.CharField(max_length=128, null=True, blank=True)
    position_type = models.PositiveSmallIntegerField(
        choices=POSITION_TYPE_CHOICES, null=True, blank=True,
        help_text='Employee position working arrangement (Ascender employment status)')
    employee_id = models.CharField(
        max_length=128, null=True, unique=True, blank=True, verbose_name='Employee ID',
        help_text='Ascender employee number')
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
        null=True, blank=True, help_text="Description of normal working hours")
    account_type = models.PositiveSmallIntegerField(
        choices=ACCOUNT_TYPE_CHOICES, null=True, blank=True,
        help_text='Employee network account status')
    security_clearance = models.BooleanField(
        default=False, verbose_name='security clearance granted',
        help_text='''Security clearance approved by CC Manager (confidentiality
        agreement, referee check, police clearance, etc.''')
    shared_account = models.BooleanField(
        default=False, editable=False, help_text='Automatically set from account type.')

    # Cache of Ascender data
    ascender_data = JSONField(null=True, blank=True, editable=False, help_text="Cache of staff Ascender data")
    ascender_data_updated = models.DateTimeField(null=True, editable=False)
    # Cache of on-premise AD data
    ad_guid = models.CharField(
        max_length=48, unique=True, null=True, blank=True, verbose_name="AD GUID",
        help_text="On-premise AD ObjectGUID")
    ad_data = JSONField(null=True, blank=True, editable=False, help_text="Cache of on-premise AD data")
    ad_data_updated = models.DateTimeField(null=True, editable=False)
    # Cache of Azure AD data
    azure_guid = models.CharField(
        max_length=48, unique=True, null=True, blank=True, verbose_name="Azure GUID",
        editable=False, help_text="Azure AD ObjectId")
    azure_ad_data = JSONField(null=True, blank=True, editable=False, help_text="Cache of Azure AD data")
    azure_ad_data_updated = models.DateTimeField(null=True, editable=False)
    dir_sync_enabled = models.NullBooleanField(default=None)  # True means this account is synced from on-prem to Azure AD.

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        """Override the save method with additional business logic.
        """
        if self.employee_id:
            if (self.employee_id.lower() == "n/a") or (self.employee_id.strip() == ''):
                self.employee_id = None
        if self.account_type in [5, 9, 10]:  # Shared/role-based/system account types.
            self.shared_account = True
        super(DepartmentUser, self).save(*args, **kwargs)

    @property
    def group_unit(self):
        """Return the group-level org unit, as seen in the primary address book view.
        """
        if self.org_unit and self.org_unit.division_unit:
            return self.org_unit.division_unit
        return self.org_unit

    def get_office_licence(self):
        """Return Microsoft 365 licence description consistent with other OIM communications.
        """
        if self.assigned_licences:
            if 'MICROSOFT 365 E5' in self.assigned_licences:
                return 'On-premise'
            elif 'OFFICE 365 E5' in self.assigned_licences:
                return 'On-premise'
            elif 'OFFICE 365 E1' in self.assigned_licences:
                return 'Cloud'
        return None

    def get_full_name(self):
        """Return given_name and surname, with a space in between.
        """
        full_name = '{} {}'.format(self.given_name if self.given_name else '', self.surname if self.surname else '')
        return full_name.strip()

    def generate_ad_actions(self):
        """For this DepartmentUser, generate ADAction objects that specify the changes which need to be
        carried out in order to synchronise AD (onprem/Azure) with IT Assets.
        TODO: refactor this method with reference to the ascender_onprem_diff management command,
        once Ascender becomes the source of truth.
        """
        actions = []

        if self.dir_sync_enabled:
            # On-prem AD
            if not self.ad_guid or not self.ad_data:
                return []

            if 'DisplayName' in self.ad_data and self.ad_data['DisplayName'] != self.name:
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field='DisplayName',
                    ad_field_value=self.ad_data['DisplayName'],
                    field='name',
                    field_value=self.name,
                    completed=None,
                )
                actions.append(action)

            if 'GivenName' in self.ad_data and self.ad_data['GivenName'] != self.given_name:
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field='GivenName',
                    ad_field_value=self.ad_data['GivenName'],
                    field='given_name',
                    field_value=self.given_name,
                    completed=None,
                )
                actions.append(action)

            if 'Surname' in self.ad_data and self.ad_data['Surname'] != self.surname:
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field='Surname',
                    ad_field_value=self.ad_data['Surname'],
                    field='surname',
                    field_value=self.surname,
                    completed=None,
                )
                actions.append(action)

            if 'Title' in self.ad_data and self.ad_data['Title'] != self.title:
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field='Title',
                    ad_field_value=self.ad_data['Title'],
                    field='title',
                    field_value=self.title,
                    completed=None,
                )
                actions.append(action)

            if 'telephoneNumber' in self.ad_data and not compare_values(self.ad_data['telephoneNumber'], self.telephone):
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field='OfficePhone',
                    ad_field_value=self.ad_data['telephoneNumber'],
                    field='telephone',
                    field_value=self.telephone,
                    completed=None,
                )
                actions.append(action)

            if 'Mobile' in self.ad_data and not compare_values(self.ad_data['Mobile'], self.mobile_phone):
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field='MobilePhone',
                    ad_field_value=self.ad_data['Mobile'],
                    field='mobile_phone',
                    field_value=self.mobile_phone,
                    completed=None,
                )
                actions.append(action)

            if 'Company' in self.ad_data and ((self.cost_centre is None and self.ad_data['Company']) or (self.cost_centre.code != self.ad_data['Company'])):
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field='Company',
                    ad_field_value=self.ad_data['Company'],
                    field='cost_centre',
                    field_value=self.cost_centre.code if self.cost_centre else None,
                    completed=None,
                )
                actions.append(action)

            if 'physicalDeliveryOfficeName' in self.ad_data and ((self.location is None and self.ad_data['physicalDeliveryOfficeName']) or (self.location.name != self.ad_data['physicalDeliveryOfficeName'])):
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field='Office',
                    ad_field_value=self.ad_data['physicalDeliveryOfficeName'],
                    field='location',
                    field_value=self.location.name if self.location else None,
                    completed=None,
                )
                actions.append(action)

            if 'EmployeeID' in self.ad_data and self.ad_data['EmployeeID'] != self.employee_id:
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field='EmployeeID',
                    ad_field_value=self.ad_data['EmployeeID'],
                    field='employee_id',
                    field_value=self.employee_id,
                    completed=None,
                )
                actions.append(action)

            if 'Manager' in self.ad_data:
                if self.ad_data['Manager'] and DepartmentUser.objects.filter(active=True, ad_data__DistinguishedName=self.ad_data['Manager']).exists():
                    manager_ad = DepartmentUser.objects.get(ad_data__DistinguishedName=self.ad_data['Manager'])
                else:
                    manager_ad = None

                if self.manager != manager_ad:
                    action, created = ADAction.objects.get_or_create(
                        department_user=self,
                        action_type='Change account field',
                        ad_field='Manager',
                        ad_field_value=self.manager.ad_guid if self.manager else None,
                        field='manager',
                        field_value=self.manager.email if self.manager else None,
                        completed=None,
                    )
                    actions.append(action)
        else:
            # Azure AD
            if not self.azure_guid or not self.azure_ad_data:
                return []

            if 'displayName' in self.azure_ad_data and self.azure_ad_data['displayName'] != self.name:
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field='DisplayName',
                    ad_field_value=self.azure_ad_data['displayName'],
                    field='name',
                    field_value=self.name,
                    completed=None,
                )
                actions.append(action)

            if 'givenName' in self.azure_ad_data and self.azure_ad_data['givenName'] != self.given_name:
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field='GivenName',
                    ad_field_value=self.azure_ad_data['givenName'],
                    field='given_name',
                    field_value=self.given_name,
                    completed=None,
                )
                actions.append(action)

            if 'surname' in self.azure_ad_data and self.azure_ad_data['surname'] != self.surname:
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field='Surname',
                    ad_field_value=self.azure_ad_data['surname'],
                    field='surname',
                    field_value=self.surname,
                    completed=None,
                )
                actions.append(action)

            if 'jobTitle' in self.azure_ad_data and self.azure_ad_data['jobTitle'] != self.title:
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field='JobTitle',
                    ad_field_value=self.azure_ad_data['jobTitle'],
                    field='title',
                    field_value=self.title,
                    completed=None,
                )
                actions.append(action)

            if 'telephoneNumber' in self.azure_ad_data and not compare_values(self.azure_ad_data['telephoneNumber'], self.telephone):
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field='TelephoneNumber',
                    ad_field_value=self.azure_ad_data['telephoneNumber'],
                    field='telephone',
                    field_value=self.telephone,
                    completed=None,
                )
                actions.append(action)

            if 'mobilePhone' in self.azure_ad_data and not compare_values(self.azure_ad_data['mobilePhone'], self.mobile_phone):
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field='Mobile',
                    ad_field_value=self.azure_ad_data['mobilePhone'],
                    field='mobile_phone',
                    field_value=self.mobile_phone,
                    completed=None,
                )
                actions.append(action)

            if 'companyName' in self.azure_ad_data and ((self.cost_centre is None and self.azure_ad_data['companyName']) or (self.azure_ad_data['companyName'] != self.cost_centre.code)):
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field='CompanyName',
                    ad_field_value=self.azure_ad_data['companyName'],
                    field='cost_centre',
                    field_value=self.cost_centre.code if self.cost_centre else None,
                    completed=None,
                )
                actions.append(action)

            if 'officeLocation' in self.azure_ad_data and ((self.location is None and self.azure_ad_data['officeLocation']) or (self.azure_ad_data['officeLocation'] != self.location.name)):
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field='StreetAddress',
                    ad_field_value=self.azure_ad_data['officeLocation'],
                    field='location',
                    field_value=self.location.name if self.location else None,
                    completed=None,
                )
                actions.append(action)

            if 'employeeId' in self.azure_ad_data and self.azure_ad_data['employeeId'] != self.employee_id:
                action, created = ADAction.objects.get_or_create(
                    department_user=self,
                    action_type='Change account field',
                    ad_field='EmployeeId',
                    ad_field_value=self.azure_ad_data['employeeId'],
                    field='employee_id',
                    field_value=self.employee_id,
                    completed=None,
                )
                actions.append(action)

            if 'manager' in self.azure_ad_data:
                if self.azure_ad_data['manager'] and DepartmentUser.objects.filter(azure_guid=self.azure_ad_data['manager']['id']).exists():
                    manager_ad = DepartmentUser.objects.get(azure_guid=self.azure_ad_data['manager']['id'])
                else:
                    manager_ad = None

                if self.manager != manager_ad:
                    action, created = ADAction.objects.get_or_create(
                        department_user=self,
                        action_type='Change account field',
                        ad_field='Manager',
                        ad_field_value=self.manager.ad_guid if self.manager else None,
                        field='manager',
                        field_value=self.manager.email if self.manager else None,
                        completed=None,
                    )
                    actions.append(action)

        return actions

    def audit_ad_actions(self):
        """For this DepartmentUser object, check any incomplete ADAction
        objects that specify changes to be made for the AD user. If the ADAction is no longer
        required (e.g. changes have been completed/reverted), delete the ADAction object.
        """
        actions = ADAction.objects.filter(department_user=self, completed__isnull=True)

        if self.dir_sync_enabled:
            # Onprem AD
            if not self.ad_guid or not self.ad_data:
                return

            for action in actions:
                if action.field == 'name' and self.ad_data['DisplayName'] == self.name:
                    action.delete()
                elif action.field == 'given_name' and self.ad_data['GivenName'] == self.given_name:
                    action.delete()
                elif action.field == 'surname' and self.ad_data['Surname'] == self.surname:
                    action.delete()
                elif action.field == 'title' and self.ad_data['Title'] == self.title:
                    action.delete()
                elif action.field == 'telephone' and compare_values(self.ad_data['telephoneNumber'], self.telephone):
                    action.delete()
                elif action.field == 'mobile_phone' and compare_values(self.ad_data['Mobile'], self.mobile_phone):
                    action.delete()
                elif action.field == 'cost_centre' and (self.cost_centre and self.ad_data['Company'] == self.cost_centre.code):
                    action.delete()
                elif action.field == 'location' and (self.location and self.ad_data['physicalDeliveryOfficeName'] == self.location.name):
                    action.delete()
                elif action.field == 'employee_id' and self.ad_data['EmployeeID'] == self.employee_id:
                    action.delete()
        else:
            # Azure AD
            if not self.azure_guid or not self.azure_ad_data:
                return

            for action in actions:
                if action.field == 'name' and self.azure_ad_data['displayName'] == self.name:
                    action.delete()
                elif action.field == 'given_name' and self.azure_ad_data['givenName'] == self.given_name:
                    action.delete()
                elif action.field == 'surname' and self.azure_ad_data['surname'] == self.surname:
                    action.delete()
                elif action.field == 'title' and self.azure_ad_data['jobTitle'] == self.title:
                    action.delete()
                elif action.field == 'telephone' and compare_values(self.azure_ad_data['telephoneNumber'], self.telephone):
                    action.delete()
                elif action.field == 'mobile_phone' and compare_values(self.azure_ad_data['mobilePhone'], self.mobile_phone):
                    action.delete()
                elif action.field == 'cost_centre' and (self.cost_centre and self.azure_ad_data['companyName'] == self.cost_centre.code):
                    action.delete()
                elif action.field == 'location' and (self.location and self.azure_ad_data['officeLocation'] == self.location.name):
                    action.delete()
                elif action.field == 'employee_id' and self.azure_ad_data['employeeId'] == self.employee_id:
                    action.delete()

    def update_from_ascender_data(self):
        """For this DepartmentUser object, update the field values from cached Ascender data
        (the source of truth for these values).
        """
        if not self.employee_id or not self.ascender_data:
            return

        if 'paypoint' in self.ascender_data and CostCentre.objects.filter(ascender_code=self.ascender_data['paypoint']).exists():
            self.cost_centre = CostCentre.objects.get(ascender_code=self.ascender_data['paypoint'])

        self.save()

    def update_deptuser_from_azure(self):
        """For this DepartmentUser object, update the field values from cached Azure AD data
        (the source of truth for these values).
        """
        if not self.azure_guid or not self.azure_ad_data:
            return

        if 'accountEnabled' in self.azure_ad_data and self.azure_ad_data['accountEnabled'] != self.active:
            self.active = self.azure_ad_data['accountEnabled']
        if 'mail'in self.azure_ad_data and self.azure_ad_data['mail'] != self.email:
            self.email = self.azure_ad_data['mail']
        if 'onPremisesSyncEnabled' in self.azure_ad_data and self.azure_ad_data['onPremisesSyncEnabled'] != self.dir_sync_enabled:
            self.dir_sync_enabled = self.azure_ad_data['onPremisesSyncEnabled']
        if 'proxyAddresses' in self.azure_ad_data and self.azure_ad_data['proxyAddresses'] != self.proxy_addresses:
            self.proxy_addresses = self.azure_ad_data['proxyAddresses']

        # Just replace the assigned_licences value every time (no comparison).
        # We replace the SKU GUID values with (known) human-readable licence types, as appropriate.
        self.assigned_licences = []
        if 'assignedLicenses' in self.azure_ad_data:
            for sku in self.azure_ad_data['assignedLicenses']:
                if sku in self.MS_LICENCE_SKUS:
                    self.assigned_licences.append(self.MS_LICENCE_SKUS[sku])
                else:
                    self.assigned_licences.append(sku)

        self.save()

    def update_deptuser_from_onprem_ad(self):
        """For this DepartmentUser object, update the field values from cached on-premise AD data
        (the source of truth for these values).
        """
        if not self.ad_guid or not self.ad_data:
            return

        if 'SamAccountName' in self.ad_data and self.ad_data['SamAccountName'] != self.username:
            self.username = self.ad_data['SamAccountName']

        self.save()

    def get_onprem_ad_domain(self):
        """If this user has onprem AD data cached, attempt to return the AD domain from their DistinguishedName.
        """
        if self.ad_data and 'DistinguishedName' in self.ad_data:
            return '.'.join([i.replace('DC=', '') for i in self.ad_data['DistinguishedName'].split(',') if i.startswith('DC=')])

        return None


class ADAction(models.Model):
    """Represents a single "action" or change that needs to be carried out to the Active Directory
    object which matches a DepartmentUser object.
    """
    ACTION_TYPE_CHOICES = (
        ('Change email', 'Change email'),  # Separate from 'change field' because this is a significant operation.
        ('Change account field', 'Change account field'),
        ('Disable account', 'Disable account'),
        ('Enable account', 'Enable account'),
    )
    created = models.DateTimeField(auto_now_add=True)
    department_user = models.ForeignKey(DepartmentUser, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=128, choices=ACTION_TYPE_CHOICES)
    ad_field = models.CharField(max_length=128, blank=True, null=True, help_text='Name of the field in Active Directory')
    ad_field_value = models.TextField(blank=True, null=True, help_text='Value of the field in Active Directory')
    field = models.CharField(max_length=128, blank=True, null=True, help_text='Name of the field in IT Assets')
    field_value = models.TextField(blank=True, null=True, help_text='Value of the field in IT Assets')
    completed = models.DateTimeField(null=True, blank=True, editable=False)
    completed_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True, editable=False)

    class Meta:
        verbose_name = 'AD action'
        verbose_name_plural = 'AD actions'

    def __str__(self):
        return '{}: {} ({} -> {})'.format(
            self.department_user.azure_guid, self.action_type, self.ad_field, self.field_value
        )

    @property
    def azure_guid(self):
        return self.department_user.azure_guid

    @property
    def ad_guid(self):
        return self.department_user.ad_guid

    @property
    def action(self):
        return '{} {} to {}'.format(self.action_type, self.ad_field, self.field_value)

    def powershell_instructions(self):
        """Returns a PowerShell command to update the relevant Active Directory.
        """
        if self.department_user.dir_sync_enabled:  # Powershell instructions for onprem AD.
            if not self.department_user.ad_guid:
                return ''
            if self.ad_field == 'Manager':
                instructions = '$manager = Get-ADUser -Identity {}\nSet-ADUser -Identity {} -Manager $manager'.format(
                    self.department_user.manager.ad_guid, self.department_user.ad_guid)
            else:
                if self.field_value:
                    instructions = 'Set-ADUser -Identity {} -{} "{}"'.format(self.department_user.ad_guid, self.ad_field, self.field_value)
                else:
                    instructions = 'Set-ADUser -Identity {} -{} $null'.format(self.department_user.ad_guid, self.ad_field)
        else:  # Powershell instructions for Azure AD.
            if self.ad_field == 'Manager':
                instructions = 'Set-AzureADUserManager -ObjectId "{}" -RefObjectId "{}"'.format(self.department_user.azure_guid, self.department_user.manager.azure_guid)
            elif self.ad_field == 'EmployeeId':
                instructions = 'Set-AzureADUserExtension -ObjectId "{}" -ExtensionName "EmployeeId" -ExtensionValue "{}"'.format(self.department_user.azure_guid, self.field_value)
            else:
                if self.field_value:
                    instructions = 'Set-AzureADUser -ObjectId "{}" -{} "{}"'.format(self.department_user.azure_guid, self.ad_field, self.field_value)
                else:
                    instructions = 'Set-AzureADUser -ObjectId "{}" -{} $null'.format(self.department_user.azure_guid, self.ad_field)
            instructions = 'Connect-AzureAD\n' + instructions

        return instructions


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
    #voip_platform = models.CharField(
    #    max_length=128, null=True, blank=True, choices=VOIP_PLATFORM_CHOICES)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def as_dict(self):
        return {k: getattr(self, k) for k in (
            'id', 'name', 'address', 'pobox', 'phone', 'fax', 'email') if getattr(self, k)}


class OrgUnit(models.Model):
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
    name = models.CharField(max_length=256)
    acronym = models.CharField(max_length=16, null=True, blank=True)
    manager = models.ForeignKey(
        DepartmentUser, on_delete=models.PROTECT, null=True, blank=True)
    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, null=True, blank=True)
    division_unit = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='division_orgunits',
        help_text='Division-level unit to which this unit belongs',
    )
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ('name',)

    def cc(self):
        return ', '.join([str(x) for x in self.costcentre_set.all()])

    def __str__(self):
        return self.name


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


class CostCentre(models.Model):
    """Models the details of a Department cost centre / chart of accounts.
    """
    code = models.CharField(max_length=16, unique=True)
    chart_acct_name = models.CharField(
        max_length=256, blank=True, null=True, verbose_name='chart of accounts name')
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
