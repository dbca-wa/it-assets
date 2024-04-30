from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.contrib.gis.db import models
from io import BytesIO
import json
import logging
import requests

from itassets.utils import ms_graph_client_token, smart_truncate, upload_blob
from .utils import compare_values, parse_windows_ts, title_except
from .microsoft_products import MS_PRODUCTS
LOGGER = logging.getLogger('organisation')


class DepartmentUser(models.Model):
    """Represents a user account managed in Active Directory / Entra ID.
    """
    ACTIVE_FILTER = {'active': True, 'contractor': False}
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
    # The following is a list of account types to normally exclude from user queries.
    # E.g. shared accounts, meeting rooms, terminated accounts, etc.
    ACCOUNT_TYPE_EXCLUDE = [
        4,  # Terminated
        5,  # Shared
        7,  # Volunteer
        1,  # Other/alumni
        9,  # Role-based
        10,  # System
        11,  # Room
        12,  # Equipment
        14,  # Unknown, disabled
        16,  # Unknown, active
    ]
    # The following is a list of user account types for individual staff/vendors,
    # i.e. no shared or role-based account types.
    # NOTE: it may not necessarily be the inverse of the previous list.
    ACCOUNT_TYPE_USER = [
        2,  # Permanent
        3,  # Agency contract
        0,  # Department contract
        8,  # Seasonal
        6,  # Vendor
        7,  # Volunteer
        1,  # Other/alumni
    ]
    # The following is a list of user account types where it may be reasonable for there to be
    # an active Azure AD account without the user also having a current Ascender job.
    ACCOUNT_TYPE_NONSTAFF = [
        8,  # Seasonal
        6,  # Vendor
        7,  # Volunteer
        1,  # Other/alumni
    ]

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    # Fields directly related to the employee, which map to a field in Active Directory.
    active = models.BooleanField(
        default=True, editable=False, help_text='Account is enabled within Active Directory / Entra ID')
    email = models.EmailField(unique=True, editable=False, help_text='Account email address')
    name = models.CharField(
        max_length=128, verbose_name='display name', help_text='Display name within AD / Outlook')
    given_name = models.CharField(max_length=128, null=True, blank=True, help_text='First name')
    surname = models.CharField(max_length=128, null=True, blank=True, help_text='Last name')
    preferred_name = models.CharField(max_length=256, null=True, blank=True)
    maiden_name = models.CharField(
        max_length=128, null=True, blank=True,
        help_text='Optional maiden name value, for the purposes of setting display name')
    title = models.CharField(
        max_length=128, null=True, blank=True,
        help_text='Occupation position title (should match Ascender position title)')
    telephone = models.CharField(
        max_length=128, null=True, blank=True, help_text='Work telephone number')
    mobile_phone = models.CharField(
        max_length=128, null=True, blank=True, help_text='Work mobile number')
    manager = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
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
        max_length=254, blank=True), blank=True, null=True, help_text='Assigned Microsoft 365 licences')

    # Metadata fields with no direct equivalent in AD.
    # They are used for internal reporting and the Address Book.
    extension = models.CharField(
        max_length=128, null=True, blank=True, verbose_name='VoIP extension')
    home_phone = models.CharField(max_length=128, null=True, blank=True)
    other_phone = models.CharField(max_length=128, null=True, blank=True)
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
    account_type = models.PositiveSmallIntegerField(
        choices=ACCOUNT_TYPE_CHOICES, null=True, blank=True,
        help_text='Employee network account status')
    security_clearance = models.BooleanField(
        default=False, verbose_name='security clearance granted',
        help_text='''Security clearance approved by CC Manager (confidentiality
        agreement, referee check, police clearance, etc.''')
    shared_account = models.BooleanField(
        default=False, editable=False, help_text='Automatically set from account type.')

    # Ascender data
    employee_id = models.CharField(
        max_length=128, null=True, unique=True, blank=True, verbose_name='Employee ID',
        help_text='Ascender employee number')
    ascender_data = models.JSONField(default=dict, null=True, blank=True, editable=False, help_text="Cache of staff Ascender data")
    ascender_data_updated = models.DateTimeField(
        null=True, editable=False, help_text="Timestamp of when Ascender data was last updated for this user")
    # On-premise AD data
    ad_guid = models.CharField(
        max_length=48, unique=True, null=True, blank=True, verbose_name="AD GUID",
        help_text="On-premise Active Directory unique object ID")
    ad_data = models.JSONField(default=dict, null=True, blank=True, editable=False, help_text="Cache of on-premise AD data")
    ad_data_updated = models.DateTimeField(null=True, editable=False)
    # Azure AD data
    azure_guid = models.CharField(
        max_length=48, unique=True, null=True, blank=True, verbose_name="Azure GUID",
        help_text="Azure Active Directory (Entra ID) unique object ID")
    azure_ad_data = models.JSONField(default=dict, null=True, blank=True, editable=False, help_text="Cache of Azure AD data")
    azure_ad_data_updated = models.DateTimeField(null=True, editable=False)
    dir_sync_enabled = models.BooleanField(null=True, default=None, help_text="Azure AD account is synced to on-prem AD")

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
        # If an account type is not set, set one here.
        if self.account_type is None:
            if self.active:
                self.account_type = 16  # Unknown - AD active
            elif not self.active:
                self.account_type = 14  # Unknown - AD disabled
        super(DepartmentUser, self).save(*args, **kwargs)

    def get_division(self):
        """Returns the name of the division this user belongs to, based upon their cost centre.
        """
        if self.cost_centre:
            return self.cost_centre.get_division_name_display()
        return None

    def get_business_unit(self):
        """Returns the business unit this users belongs to, based upon their Ascender org path.
        """
        if self.get_ascender_org_path():
            return title_except(self.get_ascender_org_path()[-1])
        return None

    def get_licence(self):
        """Return Microsoft 365 licence description consistent with other OIM communications.
        """
        if self.assigned_licences:
            if 'MICROSOFT 365 E5' in self.assigned_licences:
                return 'On-premise'
            elif 'MICROSOFT 365 F3' in self.assigned_licences:
                return 'Cloud'
        return None

    def get_full_name(self):
        """Return given_name and surname, with a space in between.
        """
        full_name = '{} {}'.format(self.given_name if self.given_name else '', self.surname if self.surname else '')
        return full_name.strip()

    def get_employment_status(self):
        """From Ascender data, return a description of a user's employment status.
        """
        if self.ascender_data and 'emp_status' in self.ascender_data and self.ascender_data['emp_status']:
            from .ascender import EMP_STATUS_MAP
            if self.ascender_data['emp_status'] in EMP_STATUS_MAP:
                return EMP_STATUS_MAP[self.ascender_data['emp_status']]
        return ''

    def get_ascender_full_name(self):
        """From Ascender data, return the users's full name.
        """
        if self.ascender_data:
            name = []
            if 'first_name' in self.ascender_data and self.ascender_data['first_name']:
                name.append(self.ascender_data['first_name'])
            if 'second_name' in self.ascender_data and self.ascender_data['second_name']:
                name.append(self.ascender_data['second_name'])
            if 'surname' in self.ascender_data and self.ascender_data['surname']:
                name.append(self.ascender_data['surname'])
            return ' '.join(name)
        return ''

    def get_ascender_preferred_name(self):
        if self.ascender_data and 'preferred_name' in self.ascender_data:
            return self.ascender_data['preferred_name']
        return ''

    def get_position_title(self):
        """From Ascender data, return the user's position title.
        """
        if self.ascender_data and 'occup_pos_title' in self.ascender_data and self.ascender_data['occup_pos_title']:
            return self.ascender_data['occup_pos_title']
        return ''

    def get_position_number(self):
        """From Ascender data, return the user's position number.
        """
        if self.ascender_data and 'position_no' in self.ascender_data and self.ascender_data['position_no']:
            return self.ascender_data['position_no']
        return ''

    def get_paypoint(self):
        """From Ascender data, return the user's paypoint value.
        """
        if self.ascender_data and 'paypoint' in self.ascender_data and self.ascender_data['paypoint']:
            return self.ascender_data['paypoint']
        return ''

    def get_ascender_org_path(self):
        """From Ascender data, return the users's organisation tree path as a list of section names.
        """
        path = []
        if (
            self.ascender_data
            and 'clevel1_desc' in self.ascender_data
            and 'clevel2_desc' in self.ascender_data
            and 'clevel3_desc' in self.ascender_data
            and 'clevel4_desc' in self.ascender_data
            and 'clevel5_desc' in self.ascender_data
        ):
            data = [
                self.ascender_data['clevel1_desc'],
                self.ascender_data['clevel2_desc'],
                self.ascender_data['clevel3_desc'],
                self.ascender_data['clevel4_desc'],
                self.ascender_data['clevel5_desc'],
            ]
            for d in data:
                branch = d.replace('ROTTNEST ISLAND AUTHORITY - ', '').replace('  ', ' ')
                if branch not in path and branch != 'DEPT BIODIVERSITY, CONSERVATION AND ATTRACTIONS':
                    path.append(branch)
        return path

    def get_geo_location_desc(self):
        """From Ascender data, return the user's geographical location description.
        """
        if self.ascender_data and 'geo_location_desc' in self.ascender_data:
            return self.ascender_data['geo_location_desc']
        return ''

    def get_job_start_date(self):
        """From Ascender data, return the user's job start date.
        """
        if self.ascender_data and 'job_start_date' in self.ascender_data and self.ascender_data['job_start_date']:
            return datetime.strptime(self.ascender_data['job_start_date'], '%Y-%m-%d').date()
        return ''

    def get_job_end_date(self):
        """From Ascender data, return the user's occupation/job termination/end date.
        """
        if self.ascender_data and 'job_end_date' in self.ascender_data and self.ascender_data['job_end_date']:
            return datetime.strptime(self.ascender_data['job_end_date'], '%Y-%m-%d').date()
        return ''

    def get_manager_name(self):
        """From Ascender data, return the user's occupation/job termination/end date.
        """
        if self.ascender_data and 'manager_name' in self.ascender_data and self.ascender_data['manager_name']:
            return self.ascender_data['manager_name']
        return ''

    def get_extended_leave(self):
        """From Ascender data, return the date from which a user's extended leave ends (if applicable).
        """
        if (
            self.ascender_data
            and 'extended_lv' in self.ascender_data
            and 'ext_lv_end_date' in self.ascender_data
            and self.ascender_data['extended_lv'] == 'Y'
            and self.ascender_data['ext_lv_end_date']
        ):
            return datetime.strptime(self.ascender_data['ext_lv_end_date'], '%Y-%m-%d').date()
        return ''

    def sync_ad_data(self, container='azuread', log_only=False, token=None):
        """For this DepartmentUser, iterate through fields which need to be synced between IT Assets
        and external AD databases (Azure AD, onprem AD).
        Each field has a 'source of truth'. In each case, check the source of truth and make changes
        to the required databases.
        If `log_only` is True, do not schedule changes to AD databases (output logs only).
        """
        if not token:
            token = ms_graph_client_token()
        url = f"https://graph.microsoft.com/v1.0/users/{self.azure_guid}"
        acct = 'onprem' if self.dir_sync_enabled else 'cloud'
        today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)  # We need a datetime object.

        # active (source of truth: Ascender).
        # This also includes Cloud-licenced users, which don't have an "expiry date".
        # SCENARIO 1: Ascender record indicates that a user's job has finished (is in the past) but their account is active - deactivate their account.
        if (
            self.active
            and self.employee_id
            and self.ascender_data
            and 'job_end_date' in self.ascender_data
            and self.ascender_data['job_end_date']
        ):
            job_end_date = datetime.strptime(self.ascender_data['job_end_date'], '%Y-%m-%d')

            # Where a user has a job which in which the job end date is in the past, deactivate the user's AD account.
            if job_end_date < today:
                log = f'{self} job is past end date of {job_end_date.date()}; deactivating their {acct} AD account'
                AscenderActionLog.objects.create(level="INFO", log=log, ascender_data=self.ascender_data)
                LOGGER.info(log)

                # Onprem AD users.
                if self.dir_sync_enabled and self.ad_guid and self.ad_data:
                    prop = 'Enabled'
                    change = {
                        'identity': self.ad_guid,
                        'property': prop,
                        'value': False,
                    }
                    f = BytesIO()
                    f.write(json.dumps(change, indent=2).encode('utf-8'))
                    f.flush()
                    f.seek(0)
                    if not log_only and settings.ASCENDER_DEACTIVATE_EXPIRED:  # Defaults as False, must be explicitly set True.
                        blob = f'onprem_changes/{self.ad_guid}_{prop}.json'
                        upload_blob(f, container, blob)
                        LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
                    else:
                        LOGGER.info('NO ACTION (log only)')

                # Azure (cloud only) AD users.
                elif not self.dir_sync_enabled and self.azure_guid and self.azure_ad_data:
                    if token:
                        headers = {
                            "Authorization": "Bearer {}".format(token["access_token"]),
                            "Content-Type": "application/json",
                        }
                        data = {"accountEnabled": False}
                        if not log_only:
                            requests.patch(url, headers=headers, json=data)
                            LOGGER.info(f'AZURE SYNC: {self} Azure AD account accountEnabled set to False')
                        else:
                            LOGGER.info('NO ACTION (log only)')

        # Future scenarios:
        # SCENARIO 2: Ascender record indicates that a user is on extended leave.
        # SCENARIO 3: Ascender record indicates that a user is seconded to another organisation.

        # expiry date (source of truth: Ascender).
        # Note that this is for onprem AD only; Azure AD has no concept of "expiry date".
        # SCENARIO 1: the user has a job end date value set in Ascender.
        if (
            self.employee_id
            and self.dir_sync_enabled
            and self.ascender_data
            and 'job_end_date' in self.ascender_data
            and self.ascender_data['job_end_date']
            and self.ad_data
            and 'AccountExpirationDate' in self.ad_data
        ):
            job_end_date = datetime.strptime(self.ascender_data['job_end_date'], '%Y-%m-%d').date()
            # Business rule: Ascender job_end_date is the final working day of a job. Onprem expiration date should be that date, plus one day.
            job_end_date = job_end_date + timedelta(days=1)

            if self.ad_data['AccountExpirationDate']:
                account_expiration_date = parse_windows_ts(self.ad_data['AccountExpirationDate']).date()
            else:
                account_expiration_date = None

            if job_end_date != account_expiration_date:
                # Set the onprem AD account expiration date value.
                prop = 'AccountExpirationDate'
                change = {
                    'identity': self.ad_guid,
                    'property': prop,
                    'value': job_end_date.strftime("%m/%d/%Y"),
                }
                f = BytesIO()
                f.write(json.dumps(change, indent=2).encode('utf-8'))
                f.flush()
                f.seek(0)
                if not log_only:
                    blob = f'onprem_changes/{self.ad_guid}_{prop}.json'
                    upload_blob(f, container, blob)
                    LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
                else:
                    LOGGER.info('NO ACTION (log only)')

                # Create a DepartmentUserLog object to record this update.
                if not log_only:
                    DepartmentUserLog.objects.create(
                        department_user=self,
                        log={
                            'ascender_field': 'job_end_date',
                            'old_value': account_expiration_date.strftime("%m/%d/%Y") if account_expiration_date else None,
                            'new_value': job_end_date.strftime("%m/%d/%Y"),
                            'description': 'Set expiry date for onprem AD account',
                        },
                    )

        # SCENARIO 2: the user has no job end date set in Ascender (i.e. is permanent to the department).
        elif (
            self.employee_id
            and self.dir_sync_enabled
            and self.ascender_data
            and 'job_end_date' in self.ascender_data
            and not self.ascender_data['job_end_date']
            and self.ad_data
            and 'AccountExpirationDate' in self.ad_data
        ):
            if self.ad_data['AccountExpirationDate']:
                account_expiration_date = parse_windows_ts(self.ad_data['AccountExpirationDate']).date()
            else:
                account_expiration_date = None

            if account_expiration_date:  # User has an account expiration set in onprem AD; remove this.
                # Unset the onprem AD account expiration date value.
                prop = 'AccountExpirationDate'
                change = {
                    'identity': self.ad_guid,
                    'property': prop,
                    'value': None,
                }
                f = BytesIO()
                f.write(json.dumps(change, indent=2).encode('utf-8'))
                f.flush()
                f.seek(0)
                if not log_only:
                    blob = f'onprem_changes/{self.ad_guid}_{prop}.json'
                    upload_blob(f, container, blob)
                    LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
                else:
                    LOGGER.info('NO ACTION (log only)')

                # Create a DepartmentUserLog object to record this update.
                if not log_only:
                    DepartmentUserLog.objects.create(
                        department_user=self,
                        log={
                            'ascender_field': 'job_end_date',
                            'old_value': account_expiration_date.strftime("%m/%d/%Y"),
                            'new_value': None,
                            'description': 'Set expiry date for onprem AD account',
                        },
                    )

        # display_name (source of truth: Ascender)
        # Onprem AD users
        if self.dir_sync_enabled and self.ad_guid and self.ad_data and 'DisplayName' in self.ad_data and self.ad_data['DisplayName'] != self.name:
            prop = 'DisplayName'
            change = {
                'identity': self.ad_guid,
                'property': prop,
                'value': self.name,
            }
            f = BytesIO()
            f.write(json.dumps(change, indent=2).encode('utf-8'))
            f.flush()
            f.seek(0)
            if not log_only:
                blob = f'onprem_changes/{self.ad_guid}_{prop}.json'
                upload_blob(f, container, blob)
                LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
            else:
                LOGGER.info('NO ACTION (log only)')
        # Azure (cloud only) AD users.
        elif not self.dir_sync_enabled and self.azure_guid and self.azure_ad_data and 'displayName' in self.azure_ad_data and self.azure_ad_data['displayName'] != self.name:
            if token:
                headers = {
                    "Authorization": "Bearer {}".format(token["access_token"]),
                    "Content-Type": "application/json",
                }
                data = {"displayName": self.name}
                if not log_only:
                    requests.patch(url, headers=headers, json=data)
                    LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account displayName set to {self.name}')
                else:
                    LOGGER.info('NO ACTION (log only)')

        # given_name (source of truth: Ascender)
        # Note that we use "preferred name" in place of legal first name here, and this should flow through to AD.
        # given_name is set by the `update_from_ascender_data` method.
        # Onprem AD users
        if self.dir_sync_enabled and self.ad_guid and self.ad_data and 'GivenName' in self.ad_data and self.ad_data['GivenName'] != self.given_name:
            prop = 'GivenName'
            change = {
                'identity': self.ad_guid,
                'property': prop,
                'value': self.given_name,
            }
            f = BytesIO()
            f.write(json.dumps(change, indent=2).encode('utf-8'))
            f.flush()
            f.seek(0)
            if not log_only:
                blob = f'onprem_changes/{self.ad_guid}_{prop}.json'
                upload_blob(f, container, blob)
                LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
            else:
                LOGGER.info('NO ACTION (log only)')
        # Azure (cloud only) AD users.
        elif not self.dir_sync_enabled and self.azure_guid and self.azure_ad_data and 'givenName' in self.azure_ad_data and self.azure_ad_data['givenName'] != self.given_name:
            if token:
                headers = {
                    "Authorization": "Bearer {}".format(token["access_token"]),
                    "Content-Type": "application/json",
                }
                data = {"givenName": self.given_name}
                if not log_only:
                    requests.patch(url, headers=headers, json=data)
                    LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account givenName set to {self.given_name}')
                else:
                    LOGGER.info('NO ACTION (log only)')

        # surname (source of truth: Ascender)
        # Onprem AD users
        if self.dir_sync_enabled and self.ad_guid and self.ad_data and 'Surname' in self.ad_data and self.ad_data['Surname'] != self.surname:
            prop = 'Surname'
            change = {
                'identity': self.ad_guid,
                'property': prop,
                'value': self.surname,
            }
            f = BytesIO()
            f.write(json.dumps(change, indent=2).encode('utf-8'))
            f.flush()
            f.seek(0)
            if not log_only:
                blob = f'onprem_changes/{self.ad_guid}_{prop}.json'
                upload_blob(f, container, blob)
                LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
            else:
                LOGGER.info('NO ACTION (log only)')
        # Azure (cloud only) AD users.
        elif not self.dir_sync_enabled and self.azure_guid and self.azure_ad_data and 'surname' in self.azure_ad_data and self.azure_ad_data['surname'] != self.surname:
            if token:
                headers = {
                    "Authorization": "Bearer {}".format(token["access_token"]),
                    "Content-Type": "application/json",
                }
                data = {"surname": self.surname}
                if not log_only:
                    requests.patch(url, headers=headers, json=data)
                    LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account surname set to {self.surname}')
                else:
                    LOGGER.info('NO ACTION (log only)')

        # cost_centre (source of truth: Ascender, recorded in AD to the Company field).
        if (
            self.employee_id
            and self.dir_sync_enabled
            and self.cost_centre
            and self.ad_guid
            and self.ad_data
            and 'Company' in self.ad_data
            and self.ad_data['Company'] != self.cost_centre.code
        ):
            prop = 'Company'
            change = {
                'identity': self.ad_guid,
                'property': prop,
                'value': self.cost_centre.code,
            }
            f = BytesIO()
            f.write(json.dumps(change, indent=2).encode('utf-8'))
            f.flush()
            f.seek(0)
            if not log_only:
                blob = f'onprem_changes/{self.ad_guid}_{prop}.json'
                upload_blob(f, container, blob)
                LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
            else:
                LOGGER.info('NO ACTION (log only)')
        # Azure (cloud only) AD users. Update the user account directly using the MS Graph API.
        elif (
            self.employee_id
            and not self.dir_sync_enabled
            and self.cost_centre
            and self.azure_guid
            and self.azure_ad_data
            and 'companyName' in self.azure_ad_data
            and self.azure_ad_data['companyName'] != self.cost_centre.code
        ):
            if token:
                headers = {
                    "Authorization": "Bearer {}".format(token["access_token"]),
                    "Content-Type": "application/json",
                }
                data = {"companyName": self.cost_centre.code}
                if not log_only:
                    requests.patch(url, headers=headers, json=data)
                    LOGGER.info(f'AZURE SYNC: {self} Azure AD account companyName set to {self.cost_centre.code}')
                else:
                    LOGGER.info('NO ACTION (log only)')

        # division (source of truth: Ascender, recorded in AD to the Department field).
        # Onprem AD users
        if (
            self.dir_sync_enabled
            and self.ad_guid
            and self.ad_data
            and self.get_division()
            and 'Department' in self.ad_data
            and self.ad_data['Department'] != self.get_division()
        ):
            prop = 'Department'
            change = {
                'identity': self.ad_guid,
                'property': prop,
                'value': self.get_division(),
            }
            f = BytesIO()
            f.write(json.dumps(change, indent=2).encode('utf-8'))
            f.flush()
            f.seek(0)
            if not log_only:
                blob = f'onprem_changes/{self.ad_guid}_{prop}.json'
                upload_blob(f, container, blob)
                LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
            else:
                LOGGER.info('NO ACTION (log only)')
        # Azure (cloud only) AD users.
        elif (
            not self.dir_sync_enabled
            and self.azure_guid
            and self.azure_ad_data
            and 'department' in self.azure_ad_data
            and self.get_division()
            and self.azure_ad_data['department'] != self.get_division()
        ):
            if token:
                headers = {
                    "Authorization": "Bearer {}".format(token["access_token"]),
                    "Content-Type": "application/json",
                }
                data = {"department": self.get_division()}
                if not log_only:
                    requests.patch(url, headers=headers, json=data)
                    LOGGER.info(f'AZURE SYNC: {self} Azure AD account department set to {self.get_division()}')
                else:
                    LOGGER.info('NO ACTION (log only)')

        # title (source of truth: Ascender)
        # Onprem AD users
        if self.dir_sync_enabled and self.ad_guid and self.ad_data and 'Title' in self.ad_data and self.ad_data['Title'] != self.title:
            prop = 'Title'
            change = {
                'identity': self.ad_guid,
                'property': prop,
                'value': self.title,
            }
            f = BytesIO()
            f.write(json.dumps(change, indent=2).encode('utf-8'))
            f.flush()
            f.seek(0)
            if not log_only:
                blob = f'onprem_changes/{self.ad_guid}_{prop}.json'
                upload_blob(f, container, blob)
                LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
            else:
                LOGGER.info('NO ACTION (log only)')
        # Azure (cloud only) AD users.
        elif not self.dir_sync_enabled and self.azure_guid and self.azure_ad_data and 'jobTitle' in self.azure_ad_data and self.azure_ad_data['jobTitle'] != self.title:
            if token:
                headers = {
                    "Authorization": "Bearer {}".format(token["access_token"]),
                    "Content-Type": "application/json",
                }
                data = {"jobTitle": self.title}
                if not log_only:
                    requests.patch(url, headers=headers, json=data)
                    LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account jobTitle set to {self.title}')
                else:
                    LOGGER.info('NO ACTION (log only)')

        # telephone (source of truth: IT Assets)
        # Onprem AD users
        if self.dir_sync_enabled and self.ad_guid and self.ad_data and 'telephoneNumber' in self.ad_data:
            if (
                self.ad_data['telephoneNumber']
                and not compare_values(self.ad_data['telephoneNumber'].strip(), self.telephone)
            ) or (
                self.telephone
                and not self.ad_data['telephoneNumber']
            ):
                prop = 'telephoneNumber'
                change = {
                    'identity': self.ad_guid,
                    'property': prop,
                    'value': self.telephone,
                }
                f = BytesIO()
                f.write(json.dumps(change, indent=2).encode('utf-8'))
                f.flush()
                f.seek(0)
                if not log_only:
                    blob = f'onprem_changes/{self.ad_guid}_{prop}.json'
                    upload_blob(f, container, blob)
                    LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
                else:
                    LOGGER.info('NO ACTION (log only)')
        # Azure (cloud only) AD users
        elif not self.dir_sync_enabled and self.azure_guid and self.azure_ad_data and 'telephoneNumber' in self.azure_ad_data:
            if (
                self.azure_ad_data['telephoneNumber']
                and not compare_values(self.azure_ad_data['telephoneNumber'].strip(), self.telephone)
            ) or (
                self.telephone
                and not self.azure_ad_data['telephoneNumber']
            ):
                if token:
                    headers = {
                        "Authorization": "Bearer {}".format(token["access_token"]),
                        "Content-Type": "application/json",
                    }
                    data = {"businessPhones": [self.telephone if self.telephone else " "]}
                    if not log_only:
                        requests.patch(url, headers=headers, json=data)
                        LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account telephoneNumber set to {self.telephone}')
                    else:
                        LOGGER.info('NO ACTION (log only)')

        # mobile (source of truth: IT Assets)
        # Onprem AD users
        if self.dir_sync_enabled and self.ad_guid and self.ad_data and 'Mobile' in self.ad_data:
            if (
                self.ad_data['Mobile']
                and not compare_values(self.ad_data['Mobile'].strip(), self.mobile_phone)
            ) or (
                self.mobile_phone
                and not self.ad_data['Mobile']
            ):
                prop = 'Mobile'
                change = {
                    'identity': self.ad_guid,
                    'property': prop,
                    'value': self.mobile_phone,
                }
                f = BytesIO()
                f.write(json.dumps(change, indent=2).encode('utf-8'))
                f.flush()
                f.seek(0)
                if not log_only:
                    blob = f'onprem_changes/{self.ad_guid}_{prop}.json'
                    upload_blob(f, container, blob)
                    LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
                else:
                    LOGGER.info('NO ACTION (log only)')
        # Azure (cloud only) AD users
        elif not self.dir_sync_enabled and self.azure_guid and self.azure_ad_data and 'mobilePhone' in self.azure_ad_data:
            if (
                self.azure_ad_data['mobilePhone']
                and not compare_values(self.azure_ad_data['mobilePhone'].strip(), self.mobile_phone)
            ) or (
                self.mobile_phone
                and not self.azure_ad_data['mobilePhone']
            ):
                if token:
                    headers = {
                        "Authorization": "Bearer {}".format(token["access_token"]),
                        "Content-Type": "application/json",
                    }
                    data = {"mobilePhone": self.mobile_phone}
                    if not log_only:
                        requests.patch(url, headers=headers, json=data)
                        LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account mobilePhone set to {self.mobile_phone}')
                    else:
                        LOGGER.info('NO ACTION (log only)')

        # employee_id (source of truth: Ascender)
        # Onprem AD users
        if (
            self.dir_sync_enabled
            and self.ad_guid
            and self.ad_data
            and 'EmployeeID' in self.ad_data
            and self.ad_data['EmployeeID'] != self.employee_id
        ):
            prop = 'EmployeeID'
            change = {
                'identity': self.ad_guid,
                'property': prop,
                'value': self.employee_id,
            }
            f = BytesIO()
            f.write(json.dumps(change, indent=2).encode('utf-8'))
            f.flush()
            f.seek(0)
            if not log_only:
                blob = f'onprem_changes/{self.ad_guid}_{prop}.json'
                upload_blob(f, container, blob)
                LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
            else:
                LOGGER.info('NO ACTION (log only)')
        # Azure (cloud only) AD users
        elif (
            not self.dir_sync_enabled
            and self.azure_guid
            and self.azure_ad_data
            and 'employeeId' in self.azure_ad_data
            and self.azure_ad_data['employeeId'] != self.employee_id
        ):
            if token:
                headers = {
                    "Authorization": "Bearer {}".format(token["access_token"]),
                    "Content-Type": "application/json",
                }
                data = {"employeeId": self.employee_id}
                if not log_only:
                    requests.patch(url, headers=headers, json=data)
                    LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account employeeId set to {self.employee_id}')
                else:
                    LOGGER.info('NO ACTION (log only)')

        # manager (source of truth: Ascender)
        # Onprem AD users
        if self.dir_sync_enabled and self.ad_guid and self.ad_data and 'Manager' in self.ad_data:
            if self.ad_data['Manager'] and DepartmentUser.objects.filter(active=True, ad_data__DistinguishedName=self.ad_data['Manager']).exists():
                manager_ad = DepartmentUser.objects.get(ad_data__DistinguishedName=self.ad_data['Manager'])
            else:
                manager_ad = None

            if self.manager != manager_ad:
                prop = 'Manager'
                change = {
                    'identity': self.ad_guid,
                    'property': prop,
                    'value': self.manager.ad_guid if self.manager else None,
                }
                f = BytesIO()
                f.write(json.dumps(change, indent=2).encode('utf-8'))
                f.flush()
                f.seek(0)
                if not log_only:
                    blob = f'onprem_changes/{self.ad_guid}_{prop}.json'
                    upload_blob(f, container, blob)
                    LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
                else:
                    LOGGER.info('NO ACTION (log only)')
        # Azure (cloud only) AD users
        elif not self.dir_sync_enabled and self.azure_guid and self.azure_ad_data and 'manager' in self.azure_ad_data:
            if self.azure_ad_data['manager'] and DepartmentUser.objects.filter(azure_guid=self.azure_ad_data['manager']['id']).exists():
                manager_ad = DepartmentUser.objects.get(azure_guid=self.azure_ad_data['manager']['id'])
            else:
                manager_ad = None

            if self.manager and self.manager.azure_guid and self.manager != manager_ad:
                if token:
                    headers = {
                        "Authorization": "Bearer {}".format(token["access_token"]),
                        "Content-Type": "application/json",
                    }
                    manager_url = f"https://graph.microsoft.com/v1.0/users/{self.azure_guid}/manager/$ref"
                    data = {"@odata.id": f"https://graph.microsoft.com/v1.0/users/{self.manager.azure_guid}"}
                    if not log_only:
                        requests.put(manager_url, headers=headers, json=data)
                        LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account manager set to {self.manager}')
                    else:
                        LOGGER.info('NO ACTION (log only)')

        # location (source of truth: Ascender)
        # Onprem AD users
        if (
            self.dir_sync_enabled
            and self.ad_guid
            and self.ad_data
            and 'physicalDeliveryOfficeName' in self.ad_data
            and 'geo_location_desc' in self.ascender_data
            and self.ascender_data['geo_location_desc']
        ):
            if Location.objects.filter(ascender_desc=self.ascender_data['geo_location_desc']).exists():
                ascender_location = Location.objects.get(ascender_desc=self.ascender_data['geo_location_desc'])
            else:
                ascender_location = None
            if self.ad_data['physicalDeliveryOfficeName'] and Location.objects.filter(name=self.ad_data['physicalDeliveryOfficeName']).exists():
                ad_location = Location.objects.get(name=self.ad_data['physicalDeliveryOfficeName'])
            else:
                ad_location = None
            # Only update if we matched a physical location from Ascender.
            if ascender_location and ascender_location != ad_location:
                # Update both physicalDeliveryOfficeName and StreetAddress in onprem AD.
                prop = 'physicalDeliveryOfficeName'
                change = {
                    'identity': self.ad_guid,
                    'property': prop,
                    'value': ascender_location.name,
                }
                f = BytesIO()
                f.write(json.dumps(change, indent=2).encode('utf-8'))
                f.flush()
                f.seek(0)
                if not log_only:
                    blob = f'onprem_changes/{self.ad_guid}_{prop}.json'
                    upload_blob(f, container, blob)
                    LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
                else:
                    LOGGER.info('NO ACTION (log only)')
                prop = 'StreetAddress'
                change = {
                    'identity': self.ad_guid,
                    'property': prop,
                    'value': ascender_location.address,
                }
                f = BytesIO()
                f.write(json.dumps(change, indent=2).encode('utf-8'))
                f.flush()
                f.seek(0)
                if not log_only:
                    blob = f'onprem_changes/{self.ad_guid}_{prop}.json'
                    upload_blob(f, container, blob)
                    LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
                else:
                    LOGGER.info('NO ACTION (log only)')
        # Azure (cloud only) AD users
        elif (
            not self.dir_sync_enabled
            and self.azure_guid
            and self.azure_ad_data
            and 'officeLocation' in self.azure_ad_data
            and 'geo_location_desc' in self.ascender_data
            and self.ascender_data['geo_location_desc']
        ):
            if Location.objects.filter(ascender_desc=self.ascender_data['geo_location_desc']).exists():
                ascender_location = Location.objects.get(ascender_desc=self.ascender_data['geo_location_desc'])
            else:
                ascender_location = None
            if self.azure_ad_data['officeLocation'] and Location.objects.filter(name=self.azure_ad_data['officeLocation']).exists():
                ad_location = Location.objects.get(name=self.azure_ad_data['officeLocation'])
            else:
                ad_location = None
            # Only update if we matched a physical location from Ascender.
            if ascender_location and ascender_location != ad_location:
                # Update both officeLocation and streetAddress in Azure AD.
                if token:
                    headers = {
                        "Authorization": "Bearer {}".format(token["access_token"]),
                        "Content-Type": "application/json",
                    }
                    data = {
                        "officeLocation": ascender_location.name,
                        "streetAddress": ascender_location.address,
                    }
                    if not log_only:
                        requests.patch(url, headers=headers, json=data)
                        LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account officeLocation set to {ascender_location.name}')
                        LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account streetAddress set to {ascender_location.address}')
                    else:
                        LOGGER.info('NO ACTION (log only)')

    def update_from_ascender_data(self):
        """For this DepartmentUser object, update the field values from cached Ascender data
        (the source of truth for these values).
        """
        if not self.employee_id or not self.ascender_data:
            return

        # First name - note that we use "preferred name" in place of legal first name here, and this should flow through to AD.
        if 'preferred_name' in self.ascender_data and self.ascender_data['preferred_name']:
            if not self.given_name:
                given_name = ''
            else:
                given_name = self.given_name
            if self.ascender_data['preferred_name'].upper() != given_name.upper():
                first_name = self.ascender_data['preferred_name'].title()
                log = f"{self} first name {self.given_name} differs from Ascender preferred name {first_name}, updating it"
                AscenderActionLog.objects.create(level="INFO", log=log, ascender_data=self.ascender_data)
                LOGGER.info(log)
                self.given_name = first_name

        # Surname
        if 'surname' in self.ascender_data and self.ascender_data['surname']:
            if not self.surname:
                surname = ''
            else:
                surname = self.surname
            if self.ascender_data['surname'].upper() != surname.upper():
                new_surname = self.ascender_data['surname'].title()
                log = f"{self} surname {self.surname} differs from Ascender surname {new_surname}, updating it"
                AscenderActionLog.objects.create(level="INFO", log=log, ascender_data=self.ascender_data)
                LOGGER.info(log)
                self.surname = new_surname

        # Preferred name
        if 'preferred_name' in self.ascender_data and self.ascender_data['preferred_name']:
            if not self.preferred_name:
                preferred_name = ''
            else:
                preferred_name = self.preferred_name
            if self.ascender_data['preferred_name'].upper() != preferred_name.upper():
                new_preferred_name = self.ascender_data['preferred_name'].title()
                log = f"{self} preferred name {self.preferred_name} differs from Ascender preferred name {new_preferred_name}, updating it"
                AscenderActionLog.objects.create(level="INFO", log=log, ascender_data=self.ascender_data)
                LOGGER.info(log)
                self.preferred_name = new_preferred_name

        # Display name (Active Directory / Entra ID / Outlook)
        # Optional maiden name used for display name (only if the maiden_name field has a value).
        # NOTE: this value is managed by OIM, and does not come from Ascender.
        # This is an exception to our normal rules relating to the source of truth for names.
        if self.preferred_name:
            if self.maiden_name:
                self.name = f"{self.preferred_name} {self.maiden_name}"
            else:
                self.name = f"{self.preferred_name} {self.surname}"
        else:
            if self.maiden_name:
                self.name = f"{self.given_name} {self.maiden_name}"
            else:
                self.name = f"{self.given_name} {self.surname}"

        # Cost centre (Ascender records cost centre as 'paypoint').
        if 'paypoint' in self.ascender_data and CostCentre.objects.filter(ascender_code=self.ascender_data['paypoint']).exists():
            paypoint = self.ascender_data['paypoint']
            cc = CostCentre.objects.get(ascender_code=paypoint)

            # The user's current CC differs from that in Ascender (it might be None).
            if self.cost_centre != cc:
                if self.cost_centre:
                    log = f"{self} cost centre {self.cost_centre.ascender_code} differs from Ascender paypoint {paypoint}, updating it"
                    AscenderActionLog.objects.create(level="INFO", log=log, ascender_data=self.ascender_data)
                    LOGGER.info(log)
                else:
                    log = f"{self} cost centre set from Ascender paypoint {paypoint}"
                    AscenderActionLog.objects.create(level="INFO", log=log, ascender_data=self.ascender_data)
                    LOGGER.info(log)
                self.cost_centre = cc  # Change the department user's cost centre.
        elif 'paypoint' in self.ascender_data and not CostCentre.objects.filter(ascender_code=self.ascender_data['paypoint']).exists():
            LOGGER.warning('Cost centre {} is not present in the IT Assets database, creating it'.format(self.ascender_data['paypoint']))
            paypoint = self.ascender_data['paypoint']
            new_cc = CostCentre.objects.create(code=paypoint, ascender_code=paypoint)
            self.cost_centre = new_cc
            log = f"{self} cost centre set from Ascender paypoint {paypoint}"
            AscenderActionLog.objects.create(level="INFO", log=log, ascender_data=self.ascender_data)
            LOGGER.info(log)

        # Manager
        if 'manager_emp_no' in self.ascender_data and self.ascender_data['manager_emp_no'] and DepartmentUser.objects.filter(employee_id=self.ascender_data['manager_emp_no']).exists():
            manager = DepartmentUser.objects.get(employee_id=self.ascender_data['manager_emp_no'])
            # The user's current manager differs from that in Ascender (it might be set to None).
            if self.manager != manager:
                if self.manager:
                    log = f"{self} manager {self.manager} differs from Ascender, updating it to {manager}"
                    AscenderActionLog.objects.create(level="INFO", log=log, ascender_data=self.ascender_data)
                    LOGGER.info(log)
                else:
                    log = f"{self} manager set from Ascender to {manager}"
                    AscenderActionLog.objects.create(level="INFO", log=log, ascender_data=self.ascender_data)
                    LOGGER.info(log)
                self.manager = manager  # Change the department user's manager.

        # Location
        if (
            'geo_location_desc' in self.ascender_data
            and self.ascender_data['geo_location_desc']
            and Location.objects.filter(ascender_desc=self.ascender_data['geo_location_desc']).exists()
        ):
            location = Location.objects.get(ascender_desc=self.ascender_data['geo_location_desc'])
            # The user's current location differs from that in Ascender.
            if self.location != location:
                if self.location:
                    log = f"{self} location {self.location} differs from Ascender location {location}, updating it"
                    AscenderActionLog.objects.create(level="INFO", log=log, ascender_data=self.ascender_data)
                    LOGGER.info(log)
                else:
                    log = f"{self} location set from Ascender location {location}"
                    AscenderActionLog.objects.create(level="INFO", log=log, ascender_data=self.ascender_data)
                    LOGGER.info(log)
                self.location = location

        # Title
        if 'occup_pos_title' in self.ascender_data and self.ascender_data['occup_pos_title']:
            ascender_title = title_except(self.ascender_data['occup_pos_title'])
            current_title = self.title if self.title else ''
            if ascender_title.upper() != current_title.upper():
                log = f"{self} title {self.title} differs from Ascender title {ascender_title}, updating it"
                AscenderActionLog.objects.create(level="INFO", log=log, ascender_data=self.ascender_data)
                LOGGER.info(log)
                self.title = ascender_title

        self.save()

    def update_from_azure_ad_data(self):
        """For this DepartmentUser object, update the field values from cached Azure AD data
        (the source of truth for these values).
        """
        if not self.azure_guid or not self.azure_ad_data:
            return

        if 'accountEnabled' in self.azure_ad_data and self.azure_ad_data['accountEnabled'] != self.active:
            self.active = self.azure_ad_data['accountEnabled']
            LOGGER.info(f'AZURE AD SYNC: {self} active changed to {self.active}')
        if 'mail'in self.azure_ad_data and self.azure_ad_data['mail'] != self.email:
            LOGGER.info('AZURE AD SYNC: {} email changed to {}'.format(self, self.azure_ad_data['mail']))
            self.email = self.azure_ad_data['mail']
        if 'onPremisesSyncEnabled' in self.azure_ad_data:
            if not self.azure_ad_data['onPremisesSyncEnabled']:  # False/None
                self.dir_sync_enabled = False
            else:
                self.dir_sync_enabled = True
        if 'proxyAddresses' in self.azure_ad_data and self.azure_ad_data['proxyAddresses'] != self.proxy_addresses:
            self.proxy_addresses = self.azure_ad_data['proxyAddresses']

        # Just replace the assigned_licences value every time (no comparison).
        # We replace the SKU GUID values with (known) human-readable licence types, as appropriate.
        self.assigned_licences = []
        if 'assignedLicenses' in self.azure_ad_data:
            for sku in self.azure_ad_data['assignedLicenses']:
                match = False
                for name, guid in MS_PRODUCTS.items():
                    if sku == guid:
                        self.assigned_licences.append(name)
                        match = True
                if not match:
                    self.assigned_licences.append(sku)

        self.save()

    def get_ascender_jobs(self):
        """Return the associated Ascender jobs records for this DepartmentUser, sorted.
        """
        if not self.employee_id:
            return None

        from organisation.ascender import ascender_employee_fetch
        jobs_data = ascender_employee_fetch(self.employee_id)  # ('<employee_id>', [<list of jobs>])
        return jobs_data[1]


class DepartmentUserLog(models.Model):
    """Represents an event carried out on a DepartmentUser object that may need to be reported
    for audit purposes, e.g. change of security access due to change of position.
    """
    created = models.DateTimeField(auto_now_add=True)
    department_user = models.ForeignKey(DepartmentUser, on_delete=models.CASCADE)
    log = models.JSONField(default=dict, editable=False)

    def __str__(self):
        return '{} {} {}'.format(
            self.created.isoformat(),
            self.department_user,
            self.log,
        )


class AscenderActionLog(models.Model):
    """Represents a log of an action carried out (or not carried out) based on data from Ascender.
    Mainly used to report actions carried out by automated account creation scripts.
    """
    LOG_LEVELS = (
        ('INFO', 'INFO'),
        ('WARNING', 'WARNING'),
        ('ERROR', 'ERROR'),
    )
    created = models.DateTimeField(auto_now_add=True, editable=False)
    level = models.CharField(max_length=64, choices=LOG_LEVELS, editable=False)
    log = models.CharField(max_length=512, editable=False)
    ascender_data = models.JSONField(default=dict, null=True, blank=True, editable=False)

    class Meta:
        ordering = ('-created',)

    def __str__(self):
        return f"{self.created.strftime('%Y-%m-%dT%H:%M:%SZ')}: {smart_truncate(self.log)}"


class Location(models.Model):
    """A model to represent a physical location.
    This model has largely been deprecated from usage.
    """
    name = models.CharField(max_length=256, unique=True)
    address = models.TextField(blank=True)
    pobox = models.TextField(blank=True, verbose_name='PO Box')
    phone = models.CharField(max_length=128, null=True, blank=True)
    fax = models.CharField(max_length=128, null=True, blank=True)
    point = models.PointField(null=True, blank=True)
    ascender_code = models.CharField(max_length=16, null=True, blank=True, unique=True)
    ascender_desc = models.CharField(max_length=128, null=True, blank=True)  # Equivalent to geo_location_desc field in Ascender.
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


DIVISION_CHOICES = (
    ("BCS", "DBCA Biodiversity and Conservation Science"),
    ("BGPA", "Botanic Gardens and Parks Authority"),
    ("CBS", "DBCA Corporate and Business Services"),
    ("CPC", "Conservation and Parks Commission"),
    ("ODG", "Office of the Director General"),
    ("PWS", "Parks and Wildlife Service"),
    ("SG", "Strategy and Governance"),
    ("RIA", "Rottnest Island Authority"),
    ("ZPA", "Zoological Parks Authority"),
)


class CostCentre(models.Model):
    """Models the details of a Department cost centre / chart of accounts.
    """
    active = models.BooleanField(default=True)
    code = models.CharField(max_length=16, unique=True)
    chart_acct_name = models.CharField(
        max_length=256, blank=True, null=True, verbose_name='chart of accounts name')
    division_name = models.CharField(max_length=128, choices=DIVISION_CHOICES, null=True, blank=True)
    manager = models.ForeignKey(
        DepartmentUser, on_delete=models.SET_NULL, related_name='manage_ccs',
        null=True, blank=True)
    ascender_code = models.CharField(max_length=16, null=True, blank=True, unique=True)

    class Meta:
        ordering = ('code',)

    def __str__(self):
        return self.code
