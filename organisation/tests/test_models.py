import logging
import random
import string
from datetime import date, timedelta
from unittest.mock import patch
from uuid import uuid1

from django.test import TestCase
from django.utils import timezone
from mixer.backend.django import mixer

from itassets.test_api import random_dbca_email
from organisation.microsoft_products import MS_PRODUCTS
from organisation.models import AscenderActionLog, CostCentre, DepartmentUser, DepartmentUserLog, Location

# Disable non-critical logging output.
logging.disable(logging.CRITICAL)


def random_string(len=10):
    """Return a random string of arbitary length."""
    return "".join(random.choice(string.ascii_letters) for _ in range(len))


class DepartmentUserTestCase(TestCase):
    def setUp(self):
        self.user = mixer.blend(
            DepartmentUser,
            active=True,
            email=random_dbca_email,
            name="Jane Doe",
            given_name="Jane",
            surname="Doe",
            employee_id=mixer.RANDOM,
            dir_sync_enabled=True,
            azure_guid=uuid1,
        )
        # Set some valid Ascender data from the test user.
        self.user.ascender_data = {
            "award": "PSGA",
            "job_no": "01",
            "first_name": self.user.given_name.upper(),
            "preferred_name": None,
            "second_name": None,
            "surname": self.user.surname.upper(),
            "loc_desc": "RSW",
            "paypoint": "123",
            "award_desc": "PUBLIC SERVICE AWARD (PSGOGA AGREEMENT)",
            "clevel1_id": "BCA",
            "emp_status": "PFA",
            "occup_type": "SUB",
            "employee_id": "123456",
            "extended_lv": None,
            "position_no": "0000000001",
            "term_reason": None,
            "clevel1_desc": "DEPT BIODIVERSITY, CONSERVATION AND ATTRACTIONS",
            "clevel2_desc": "STRATEGY AND GOVERNANCE",
            "clevel3_desc": "OFFICE OF INFORMATION MANAGEMENT",
            "clevel4_desc": "TECHNOLOGY AND SECURITY",
            "clevel5_desc": None,
            "job_end_date": None,
            "licence_type": "ONPUL",
            "manager_name": "SMITH, Mr JOHN",
            "email_address": self.user.email,
            "emp_stat_desc": "PERMANENT FULL-TIME AUTO",
            "paypoint_desc": "Office of Information Management Branch",
            "work_phone_no": None,
            "job_start_date": "2020-01-01",
            "manager_emp_no": "012345",
            "ext_lv_end_date": None,
            "occup_pos_title": "CUSTOMER SERVICES REPRESENTATIVE",
            "geo_location_desc": "17 Dick Perry Ave,Tech Park, KENSINGTON",
            "work_mobile_phone_no": None,
        }
        self.user.ascender_data_updated = timezone.localtime()
        # Set some valid Azure data for the test user.
        self.user.azure_ad_data = {
            "objectId": self.user.azure_guid,
            "mail": self.user.email,
            "lastPasswordChangeDateTime": timezone.localtime().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self.user.azure_ad_data_updated = timezone.localtime()
        self.user.save()
        self.manager = mixer.blend(
            DepartmentUser,
            active=True,
            email=random_dbca_email,
            given_name=mixer.RANDOM,
            surname=mixer.RANDOM,
            employee_id=mixer.RANDOM,
            dir_sync_enabled=True,
            ad_data={"DistinguishedName": random_string()},
            azure_guid=uuid1,
        )
        self.cc = mixer.blend(
            CostCentre,
            active=True,
            division_name=mixer.RANDOM,
        )
        self.user.update_from_ascender_data()

    def test_save(self):
        self.assertTrue(self.user.employee_id)
        self.user.employee_id = "N/A"
        self.user.account_type = 5
        self.user.save()
        self.assertFalse(self.user.employee_id)

    def test_get_licence(self):
        self.assertFalse(self.user.get_licence())
        self.user.assigned_licences = ["MICROSOFT 365 E5", "foo"]
        self.user.save()
        self.assertEqual(self.user.get_licence(), "On-premise")
        self.user.assigned_licences = ["MICROSOFT 365 F3", "bar"]
        self.user.save()
        self.assertEqual(self.user.get_licence(), "Cloud")
        self.user.assigned_licences = ["foo", "bar"]
        self.user.save()
        self.assertFalse(self.user.get_licence())

    def test_get_display_name(self):
        self.assertEqual(self.user.get_display_name(), self.user.name)

    def test_get_display_name_preferred(self):
        self.user.preferred_name = "Janey"
        self.assertEqual(self.user.get_display_name(), "Janey Doe")

    def test_get_display_name_maiden(self):
        self.user.maiden_name = "Jones"
        self.assertEqual(self.user.get_display_name(), "Jane Jones")

    def test_get_display_name_preferred_maiden(self):
        self.user.preferred_name = "Janey"
        self.user.maiden_name = "Jones"
        self.assertEqual(self.user.get_display_name(), "Janey Jones")

    def test_get_ascender_full_name(self):
        self.assertEqual(self.user.get_ascender_full_name(), "JANE DOE")

    def test_get_division(self):
        self.assertEqual(self.user.get_division(), "Strategy and Governance")
        self.user.ascender_data["clevel2_desc"] = "ROTTNEST ISLAND AUTHORITY"
        self.assertEqual(self.user.get_division(), "Rottnest Island Authority")

    def test_get_business_unit(self):
        self.assertEqual(self.user.get_business_unit(), "Office of Information Management")

    def test_get_employment_status(self):
        self.assertTrue(self.user.get_employment_status())
        self.user.ascender_data["emp_status"] = None
        self.user.save()
        self.assertFalse(self.user.get_employment_status())

    def test_get_ascender_clevels(self):
        clevels = self.user.get_ascender_clevels()
        # Return value should be a list, and not be falsy
        self.assertTrue(isinstance(clevels, list))
        self.assertTrue(clevels)

    def test_get_ascender_org_path(self):
        org_path = self.user.get_ascender_org_path()
        # Return value should be a list, and not be falsy
        self.assertTrue(isinstance(org_path, list))
        self.assertTrue(org_path)

    def test_get_display_name_ascender_preferred(self):
        self.user.ascender_data["preferred_name"] = "JANEY"
        self.user.update_from_ascender_data()
        self.assertEqual(self.user.get_display_name(), "Janey Doe")
        self.assertEqual(self.user.get_ascender_full_name(), "JANE DOE")

    def test_get_display_name_ascender_preferred_maiden(self):
        self.user.maiden_name = "Jones"
        self.user.update_from_ascender_data()
        self.assertEqual(self.user.get_display_name(), "Jane Jones")
        self.assertEqual(self.user.get_ascender_full_name(), "JANE DOE")

    def test_get_display_name_ascender_given(self):
        self.user.update_from_ascender_data()
        self.assertEqual(self.user.get_display_name(), "Jane Doe")
        self.assertEqual(self.user.get_ascender_full_name(), "JANE DOE")

    def test_get_display_name_ascender_given_maiden(self):
        self.user.maiden_name = "Jones"
        self.user.update_from_ascender_data()
        self.assertEqual(self.user.get_display_name(), "Jane Jones")
        self.assertEqual(self.user.get_ascender_full_name(), "JANE DOE")

    def test_get_pw_last_change(self):
        self.assertTrue(self.user.get_pw_last_change())
        self.user.azure_ad_data = {}
        self.user.save()
        self.assertFalse(self.user.get_pw_last_change())


# ---------------------------------------------------------------------------
# DepartmentUser.save() – account_type mapping from emp_status
# ---------------------------------------------------------------------------


class DepartmentUserSaveAccountTypeTestCase(TestCase):
    """Tests for the account_type auto-assignment logic inside DepartmentUser.save()."""

    def _user_with_status(self, emp_status):
        user = mixer.blend(DepartmentUser, email=random_dbca_email, ascender_data={"emp_status": emp_status})
        return user

    def test_account_type_defaults_to_unknown_when_none(self):
        user = mixer.blend(DepartmentUser, email=random_dbca_email, account_type=None, ascender_data={})
        self.assertEqual(user.account_type, 14)

    def test_emp_status_ext_sets_alumni(self):
        self.assertEqual(self._user_with_status("EXT").account_type, 1)

    def test_emp_status_ao_sets_vendor(self):
        self.assertEqual(self._user_with_status("AO").account_type, 6)

    def test_emp_status_seap_sets_seasonal(self):
        self.assertEqual(self._user_with_status("SEAP").account_type, 8)

    def test_emp_status_seas_sets_seasonal(self):
        self.assertEqual(self._user_with_status("SEAS").account_type, 8)

    def test_emp_status_cfa_sets_contract(self):
        self.assertEqual(self._user_with_status("CFA").account_type, 0)

    def test_emp_status_con_sets_contract(self):
        self.assertEqual(self._user_with_status("CON").account_type, 0)

    def test_emp_status_pfa_sets_permanent(self):
        self.assertEqual(self._user_with_status("PFA").account_type, 2)

    def test_emp_status_pft_sets_permanent(self):
        self.assertEqual(self._user_with_status("PFT").account_type, 2)

    def test_telephone_stripped_on_save(self):
        user = mixer.blend(DepartmentUser, email=random_dbca_email, telephone="  08 9999 0001\r\n")
        self.assertEqual(user.telephone, "08 9999 0001")

    def test_mobile_phone_stripped_on_save(self):
        user = mixer.blend(DepartmentUser, email=random_dbca_email, mobile_phone=" 0400 000 001 ")
        self.assertEqual(user.mobile_phone, "0400 000 001")

    def test_employee_id_blank_string_cleared(self):
        user = mixer.blend(DepartmentUser, email=random_dbca_email, employee_id="   ")
        self.assertFalse(user.employee_id)


# ---------------------------------------------------------------------------
# Ascender data getter methods
# ---------------------------------------------------------------------------


class DepartmentUserAscenderGettersTestCase(TestCase):
    """Tests for the small read-only Ascender data accessor methods."""

    def setUp(self):
        self.user = mixer.blend(DepartmentUser, email=random_dbca_email)
        self.user.ascender_data = {
            "preferred_name": "JANE",
            "occup_pos_title": "SENIOR DEVELOPER",
            "position_no": "0000123",
            "paypoint": "099",
            "geo_location_desc": "17 Dick Perry Ave, KENSINGTON",
            "job_start_date": "2020-01-15",
            "job_end_date": "2025-12-31",
            "manager_name": "SMITH, Mr JOHN",
            "extended_lv": "Y",
            "ext_lv_end_date": "2025-06-30",
            "term_reason": "RS",
        }

    def test_get_ascender_preferred_name_present(self):
        self.assertEqual(self.user.get_ascender_preferred_name(), "JANE")

    def test_get_ascender_preferred_name_absent(self):
        self.user.ascender_data = {}
        self.assertIsNone(self.user.get_ascender_preferred_name())

    def test_get_ascender_preferred_name_null(self):
        self.user.ascender_data = {"preferred_name": None}
        self.assertIsNone(self.user.get_ascender_preferred_name())

    def test_get_position_title(self):
        self.assertEqual(self.user.get_position_title(), "SENIOR DEVELOPER")

    def test_get_position_title_absent(self):
        self.user.ascender_data = {}
        self.assertIsNone(self.user.get_position_title())

    def test_get_position_number(self):
        self.assertEqual(self.user.get_position_number(), "0000123")

    def test_get_position_number_absent(self):
        self.user.ascender_data = {}
        self.assertIsNone(self.user.get_position_number())

    def test_get_paypoint(self):
        self.assertEqual(self.user.get_paypoint(), "099")

    def test_get_paypoint_absent(self):
        self.user.ascender_data = {}
        self.assertIsNone(self.user.get_paypoint())

    def test_get_geo_location_desc(self):
        self.assertEqual(self.user.get_geo_location_desc(), "17 Dick Perry Ave, KENSINGTON")

    def test_get_geo_location_desc_absent(self):
        self.user.ascender_data = {}
        self.assertIsNone(self.user.get_geo_location_desc())

    def test_get_job_start_date(self):
        self.assertEqual(self.user.get_job_start_date(), date(2020, 1, 15))

    def test_get_job_start_date_absent(self):
        self.user.ascender_data = {}
        self.assertIsNone(self.user.get_job_start_date())

    def test_get_job_start_date_null(self):
        self.user.ascender_data = {"job_start_date": None}
        self.assertIsNone(self.user.get_job_start_date())

    def test_get_job_end_date(self):
        self.assertEqual(self.user.get_job_end_date(), date(2025, 12, 31))

    def test_get_job_end_date_null(self):
        self.user.ascender_data["job_end_date"] = None
        self.assertIsNone(self.user.get_job_end_date())

    def test_get_job_end_date_absent(self):
        self.user.ascender_data = {}
        self.assertIsNone(self.user.get_job_end_date())

    def test_get_manager_name(self):
        self.assertEqual(self.user.get_manager_name(), "SMITH, Mr JOHN")

    def test_get_manager_name_absent(self):
        self.user.ascender_data = {}
        self.assertIsNone(self.user.get_manager_name())

    def test_get_extended_leave_on_leave(self):
        self.assertEqual(self.user.get_extended_leave(), date(2025, 6, 30))

    def test_get_extended_leave_not_on_leave(self):
        self.user.ascender_data["extended_lv"] = "N"
        self.assertIsNone(self.user.get_extended_leave())

    def test_get_extended_leave_absent(self):
        self.user.ascender_data = {}
        self.assertIsNone(self.user.get_extended_leave())

    def test_get_term_reason_known_code(self):
        self.assertEqual(self.user.get_term_reason(), "Resignation")

    def test_get_term_reason_unknown_code_returns_none(self):
        self.user.ascender_data["term_reason"] = "ZZ"
        self.assertIsNone(self.user.get_term_reason())

    def test_get_term_reason_absent(self):
        self.user.ascender_data = {}
        self.assertIsNone(self.user.get_term_reason())

    def test_get_term_reason_null(self):
        self.user.ascender_data = {"term_reason": None}
        self.assertIsNone(self.user.get_term_reason())


# ---------------------------------------------------------------------------
# DepartmentUser.get_account_dormant()
# ---------------------------------------------------------------------------


class GetAccountDormantTestCase(TestCase):
    def setUp(self):
        self.user = mixer.blend(
            DepartmentUser,
            email=random_dbca_email,
            azure_guid=uuid1,
            azure_ad_data={"accountEnabled": True},
            last_signin=None,
            last_password_change=None,
        )

    def test_no_azure_guid_returns_none(self):
        self.user.azure_guid = None
        self.assertIsNone(self.user.get_account_dormant())

    def test_empty_azure_ad_data_returns_none(self):
        self.user.azure_ad_data = {}
        self.assertIsNone(self.user.get_account_dormant())

    def test_no_signin_or_password_change_returns_none(self):
        self.assertIsNone(self.user.get_account_dormant())

    def test_recent_signin_returns_false(self):
        self.user.last_signin = timezone.now() - timedelta(days=5)
        self.assertFalse(self.user.get_account_dormant(dormant_account_days=30))

    def test_old_signin_returns_true(self):
        self.user.last_signin = timezone.now() - timedelta(days=365)
        self.assertTrue(self.user.get_account_dormant(dormant_account_days=30))

    def test_exactly_at_threshold_returns_true(self):
        self.user.last_signin = timezone.now() - timedelta(days=30)
        self.assertTrue(self.user.get_account_dormant(dormant_account_days=30))

    def test_uses_password_change_when_no_signin(self):
        self.user.last_signin = None
        self.user.last_password_change = timezone.now() - timedelta(days=365)
        self.assertTrue(self.user.get_account_dormant(dormant_account_days=30))

    def test_recent_password_change_returns_false(self):
        self.user.last_signin = None
        self.user.last_password_change = timezone.now() - timedelta(days=5)
        self.assertFalse(self.user.get_account_dormant(dormant_account_days=30))


# ---------------------------------------------------------------------------
# DepartmentUser.update_from_entra_id_data()
# ---------------------------------------------------------------------------


class UpdateFromEntraIdDataTestCase(TestCase):
    def setUp(self):
        self.user = mixer.blend(
            DepartmentUser,
            email=random_dbca_email,
            active=True,
            azure_guid=uuid1,
            azure_ad_data={"accountEnabled": True},
            dir_sync_enabled=True,
            proxy_addresses=[],
            assigned_licences=[],
        )

    def test_noop_without_azure_guid(self):
        """Method returns early and makes no changes when azure_guid is absent."""
        self.user.azure_guid = None
        self.user.active = True
        self.user.azure_ad_data = {"accountEnabled": False}
        self.user.update_from_entra_id_data()
        self.assertTrue(self.user.active)  # unchanged

    def test_active_updated_from_entra(self):
        self.user.azure_ad_data = {"accountEnabled": False}
        self.user.update_from_entra_id_data()
        self.assertFalse(self.user.active)

    def test_email_updated_from_entra(self):
        new_email = "new.address@dbca.wa.gov.au"
        self.user.azure_ad_data = {"mail": new_email}
        self.user.update_from_entra_id_data()
        self.assertEqual(self.user.email, new_email)

    def test_dir_sync_disabled_when_null(self):
        self.user.azure_ad_data = {"onPremisesSyncEnabled": None}
        self.user.update_from_entra_id_data()
        self.assertFalse(self.user.dir_sync_enabled)

    def test_dir_sync_enabled(self):
        self.user.dir_sync_enabled = False
        self.user.azure_ad_data = {"onPremisesSyncEnabled": True}
        self.user.update_from_entra_id_data()
        self.assertTrue(self.user.dir_sync_enabled)

    def test_proxy_addresses_updated(self):
        addrs = ["smtp:alias@dbca.wa.gov.au", "smtp:alias2@dbca.wa.gov.au"]
        self.user.azure_ad_data = {"proxyAddresses": addrs}
        self.user.update_from_entra_id_data()
        self.assertEqual(self.user.proxy_addresses, addrs)

    def test_assigned_licences_known_sku_resolved_to_name(self):
        e5_guid = MS_PRODUCTS["MICROSOFT 365 E5"]
        self.user.azure_ad_data = {"assignedLicenses": [e5_guid]}
        self.user.update_from_entra_id_data()
        self.assertIn("MICROSOFT 365 E5", self.user.assigned_licences)

    def test_assigned_licences_unknown_sku_kept_raw(self):
        unknown_guid = "aaaaaaaa-0000-0000-0000-000000000000"
        self.user.azure_ad_data = {"assignedLicenses": [unknown_guid]}
        self.user.update_from_entra_id_data()
        self.assertIn(unknown_guid, self.user.assigned_licences)

    def test_assigned_licences_empty_list(self):
        self.user.azure_ad_data = {"assignedLicenses": []}
        self.user.update_from_entra_id_data()
        self.assertEqual(self.user.assigned_licences, [])

    def test_last_password_change_set_from_azure_data(self):
        self.user.azure_ad_data = {"lastPasswordChangeDateTime": "2024-03-15T10:00:00Z"}
        self.user.update_from_entra_id_data()
        self.assertIsNotNone(self.user.last_password_change)
        self.assertEqual(self.user.last_password_change.year, 2024)
        self.assertEqual(self.user.last_password_change.month, 3)


# ---------------------------------------------------------------------------
# DepartmentUser.update_from_ascender_data() – targeted edge cases
# ---------------------------------------------------------------------------


class UpdateFromAscenderDataTestCase(TestCase):
    """Targeted tests for update_from_ascender_data() scenarios not covered by setUp."""

    def _make_user(self, ascender_data):
        user = mixer.blend(DepartmentUser, email=random_dbca_email, employee_id=mixer.RANDOM)
        user.ascender_data = ascender_data
        return user

    def test_given_name_updated_from_ascender(self):
        user = self._make_user({"first_name": "ALICE", "preferred_name": None, "surname": "JONES"})
        user.given_name = "Alicia"  # differs from ALICE
        user.update_from_ascender_data()
        self.assertEqual(user.given_name, "Alice")

    def test_surname_updated_from_ascender(self):
        user = self._make_user({"first_name": "BOB", "preferred_name": None, "surname": "SMITH"})
        user.surname = "Smythe"  # differs
        user.update_from_ascender_data()
        self.assertEqual(user.surname, "Smith")

    def test_title_updated_from_ascender(self):
        user = self._make_user({"first_name": "CAROL", "preferred_name": None, "surname": "LEE", "occup_pos_title": "SENIOR MANAGER"})
        user.title = "Manager"  # differs
        user.update_from_ascender_data()
        self.assertEqual(user.title, "Senior Manager")

    def test_manager_set_from_ascender_employee_id(self):
        manager = mixer.blend(DepartmentUser, email=random_dbca_email, employee_id="MGR001")
        user = self._make_user({"first_name": "DAVE", "preferred_name": None, "surname": "BROWN", "manager_emp_no": "MGR001"})
        user.update_from_ascender_data()
        user.refresh_from_db()
        self.assertEqual(user.manager, manager)

    def test_director_general_manager_set_to_none(self):
        mixer.blend(DepartmentUser, email=random_dbca_email, employee_id="DDG001")
        user = self._make_user({"first_name": "EVE", "preferred_name": None, "surname": "WHITE", "manager_emp_no": "DDG001"})
        user.title = "Director General"
        manager_before = mixer.blend(DepartmentUser, email=random_dbca_email)
        user.manager = manager_before
        user.update_from_ascender_data()
        user.refresh_from_db()
        self.assertIsNone(user.manager)

    def test_location_set_from_ascender_geo_desc(self):
        loc = mixer.blend(Location, ascender_desc="17 Dick Perry Ave, KENSINGTON")
        user = self._make_user(
            {"first_name": "FRANK", "preferred_name": None, "surname": "BLACK", "geo_location_desc": "17 Dick Perry Ave, KENSINGTON"}
        )
        user.update_from_ascender_data()
        user.refresh_from_db()
        self.assertEqual(user.location, loc)

    def test_cost_centre_created_when_missing(self):
        user = self._make_user({"first_name": "GRACE", "preferred_name": None, "surname": "GREY", "paypoint": "ZZZ99"})
        user.update_from_ascender_data()
        user.refresh_from_db()
        self.assertIsNotNone(user.cost_centre)
        self.assertEqual(user.cost_centre.ascender_code, "ZZZ99")

    def test_cost_centre_updated_when_exists(self):
        cc = mixer.blend(CostCentre, code="CC01", ascender_code="CC01")
        user = self._make_user({"first_name": "HELEN", "preferred_name": None, "surname": "FORD", "paypoint": "CC01"})
        user.update_from_ascender_data()
        user.refresh_from_db()
        self.assertEqual(user.cost_centre, cc)


# ---------------------------------------------------------------------------
# DepartmentUser.get_graph_user() with mocked Graph API
# ---------------------------------------------------------------------------


class GetGraphUserTestCase(TestCase):
    @patch("organisation.models.ms_graph_get_user")
    def test_returns_graph_data(self, mock_get_user):
        mock_get_user.return_value = {"id": "some-guid", "displayName": "Jane Doe"}
        user = mixer.blend(DepartmentUser, email=random_dbca_email, azure_guid="some-guid")
        result = user.get_graph_user()
        mock_get_user.assert_called_once_with("some-guid")
        self.assertEqual(result["displayName"], "Jane Doe")

    def test_returns_none_without_azure_guid(self):
        user = mixer.blend(DepartmentUser, email=random_dbca_email, azure_guid=None)
        self.assertIsNone(user.get_graph_user())

# ---------------------------------------------------------------------------
# DepartmentUser.get_assigned_entra_groups() & DepartmentUser.get_copilot_group()
# ---------------------------------------------------------------------------

class GetAssignedEntraGroupsTestCase(TestCase):
    def setUp(self):
        self.user = mixer.blend(
            DepartmentUser,
            assigned_entra_groups = {"some-name-1":"some-guid-1","sg-oim-app-copilot-users":"copilot-guid-1","sg-oim-app-copilot-eval":"copilot-guid-2","some-name-2":"some-guid-2"}
        )

    def test_get_assigned_entra_groups(self):
        # Test retrieving group names
        groups = self.user.get_assigned_entra_groups()
        self.assertIn("some-name-1",groups)
        self.assertIn("some-name-2",groups)
        self.assertIn("sg-oim-app-copilot-users",groups)
        self.assertIn("sg-oim-app-copilot-eval",groups)
        self.assertEqual(len(groups),4)

        # Test retrieving group guids
        groups = self.user.get_assigned_entra_groups(guids=True)
        self.assertIn("some-guid-1",groups)
        self.assertIn("copilot-guid-1",groups)
        self.assertIn("copilot-guid-2",groups)
        self.assertIn("some-guid-2",groups)
        self.assertEqual(len(groups),4)

        # Test accurate report of empty dict
        self.user.assigned_entra_groups = {}
        groups = self.user.get_assigned_entra_groups()
        self.assertIsNone(groups)
        groups = self.user.get_assigned_entra_groups(guids=True)
        self.assertIsNone(groups)

        # Test accurate report of None field
        self.user.assigned_entra_groups = None
        groups = self.user.get_assigned_entra_groups()
        self.assertIsNone(groups)
        groups = self.user.get_assigned_entra_groups(guids=True)
        self.assertIsNone(groups)

    def test_get_copilot_group(self):
        # Test finding 1 viable copilot group
        group = self.user.get_copilot_group()
        self.assertEqual("sg-oim-app-copilot-users",group)

        # Test finding >1 viable copilot groups
        self.user.assigned_entra_groups.update({"sg-fb-app-copilot-users":"copilot-guid-3"})
        group = self.user.get_copilot_group()
        self.assertEqual(group == "sg-fb-app-copilot-users" or group == "sg-oim-app-copilot-users",True)

        # Test finding 0 viable copilot groups
        self.user.assigned_entra_groups = {"some-name-1":"some-guid-1","sg-oim-app-copilot-eval":"copilot-guid-2","some-name-2":"some-guid-2"}
        group = self.user.get_copilot_group()
        self.assertIsNone(group)

        # Test the user being in no groups
        self.user.assigned_entra_groups = None
        group = self.user.get_copilot_group()
        self.assertIsNone(group)

# ---------------------------------------------------------------------------
# Model __str__ representations
# ---------------------------------------------------------------------------


class ModelStrTestCase(TestCase):
    def test_department_user_str(self):
        user = mixer.blend(DepartmentUser, email="test@dbca.wa.gov.au")
        self.assertEqual(str(user), "test@dbca.wa.gov.au")

    def test_department_user_log_str(self):
        user = mixer.blend(DepartmentUser, email=random_dbca_email)
        log = DepartmentUserLog.objects.create(department_user=user, log={"field": "name", "old": "A", "new": "B"})
        s = str(log)
        self.assertIn(user.email, s)

    def test_ascender_action_log_str(self):
        log = AscenderActionLog.objects.create(level="INFO", log="Account created for test@dbca.wa.gov.au")
        s = str(log)
        self.assertIn("Account created", s)

    def test_location_str(self):
        loc = mixer.blend(Location, name="Perth CBD Office")
        self.assertEqual(str(loc), "Perth CBD Office")

    def test_cost_centre_str(self):
        cc = mixer.blend(CostCentre, code="OIM")
        self.assertEqual(str(cc), "OIM")
