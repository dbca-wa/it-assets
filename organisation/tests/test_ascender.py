import logging
import random
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from mixer.backend.django import mixer

from itassets.test_api import random_dbca_email
from organisation.ascender import (
    _assign_licence_with_retry,
    _build_licence_payload,
    _check_licence_availability,
    _log_and_abort,
    _resolve_names,
    _send_admin_failure_email,
    _wait_for_usage_location,
    create_entra_id_user,
    department_user_create,
    generate_valid_dbca_email,
    new_user_creation_email,
    sanitise_name_values,
    validate_ascender_user_account_rules,
)
from organisation.microsoft_products import MS_PRODUCTS
from organisation.models import AscenderActionLog, CostCentre, DepartmentUser, Location
from organisation.utils import title_except

# Disable non-critical logging output.
logging.disable(logging.CRITICAL)


class AscenderTestCase(TestCase):
    """Test functions related to the import of department user data from Ascender."""

    def setUp(self):
        # Generate a Django user for endpoint responses.
        self.user = User.objects.create_user(username="admin", email="admin@dbca.wa.gov.au", password="pass")
        loc_desc = "1 Fake Street, DULLSVILLE"
        self.location = mixer.blend(
            Location,
            name=loc_desc,
            ascender_desc=loc_desc,
        )
        cc_code = str(random.randint(100, 999))
        self.cc = mixer.blend(CostCentre, code=cc_code, ascender_code=cc_code)
        self.manager = mixer.blend(
            DepartmentUser,
            active=True,
            email=random_dbca_email,
            given_name=mixer.RANDOM,
            surname=mixer.RANDOM,
            employee_id=str(random.randint(100000, 999999)),
        )
        self.next_week = date.today() + timedelta(days=7)
        self.ascender_data = {
            "employee_id": str(random.randint(100000, 999999)),
            "first_name": mixer.faker.first_name().upper(),
            "second_name": mixer.faker.first_name().upper(),
            "surname": mixer.faker.last_name().upper(),
            "preferred_name": None,
            "occup_pos_title": mixer.faker.title().upper(),
            "emp_stat_desc": "CASUAL EMPLOYEES",
            "geo_location_desc": loc_desc,
            "paypoint": cc_code,
            "clevel1_id": "BCA",
            "clevel1_desc": "DEPT BIODIVERSITY, CONSERVATION AND ATTRACTIONS",
            "clevel2_desc": "STRATEGY AND GOVERNANCE",
            "clevel3_desc": "OFFICE OF EXPECTATION MANAGEMENT",
            "clevel4_desc": "CENTRAL OFFICE",
            "clevel5_desc": None,
            "emp_status": "PFA",
            "position_no": str(random.randint(10000000, 99999999)),
            "job_start_date": self.next_week.strftime("%Y-%m-%d"),
            "job_end_date": None,
            "licence_type": "ONPUL",
            "manager_emp_no": str(self.manager.employee_id),
        }
        self.email, _ = generate_valid_dbca_email(surname=self.ascender_data["surname"], first_name=self.ascender_data["first_name"])
        self.display_name = f"{self.ascender_data['first_name'].title().strip()} {self.ascender_data['surname'].title().strip()}"
        self.title = title_except(self.ascender_data["occup_pos_title"])

    def create_new_user(self):
        return department_user_create(
            job=self.ascender_data,
            azure_guid=str(uuid4()),
            email=self.email,
            display_name=self.display_name,
            title=self.title,
            cc=self.cc,
            location=self.location,
            manager=self.manager,
        )

    def test_validate_ascender_user_account_rules(self):
        """Test the validate_ascender_user_account_rules function"""
        self.assertTrue(validate_ascender_user_account_rules(self.ascender_data))

    def test_validate_ascender_user_account_rules_fpc(self):
        """Test the validate_ascender_user_account_rules function for an FPC record"""
        self.ascender_data["clevel1_id"] = "FPC"
        self.assertFalse(validate_ascender_user_account_rules(self.ascender_data))

    def test_validate_ascender_user_account_rules_user_exists(self):
        """Test the validate_ascender_user_account_rules function where a user already exists"""
        mixer.blend(
            DepartmentUser,
            active=True,
            email=random_dbca_email,
            given_name=mixer.RANDOM,
            surname=mixer.RANDOM,
            employee_id=self.ascender_data["employee_id"],
        )
        self.assertFalse(validate_ascender_user_account_rules(self.ascender_data))

    def test_validate_ascender_user_account_rules_job_ended(self):
        """Test the validate_ascender_user_account_rules function where a user's job end date is past"""
        last_week = date.today() - timedelta(days=7)
        self.ascender_data["job_end_date"] = last_week.strftime("%Y-%m-%d")
        self.assertFalse(validate_ascender_user_account_rules(self.ascender_data))

    def test_validate_ascender_user_account_rules_no_licence(self):
        """Test the validate_ascender_user_account_rules function where no M365 licence is assigned"""
        self.ascender_data["licence_type"] = None
        self.assertFalse(validate_ascender_user_account_rules(self.ascender_data))

    def test_validate_ascender_user_account_rules_licence_invalid(self):
        """Test the validate_ascender_user_account_rules function where an invalid licence type is assigned"""
        self.ascender_data["licence_type"] = "FOOBAR"
        self.assertFalse(validate_ascender_user_account_rules(self.ascender_data))

    def test_validate_ascender_user_account_rules_no_manager(self):
        """Test the validate_ascender_user_account_rules function where no known manager is assigned"""
        self.ascender_data["manager_emp_no"] = None
        self.assertFalse(validate_ascender_user_account_rules(self.ascender_data))
        self.ascender_data["manager_emp_no"] = "000001"
        self.assertFalse(validate_ascender_user_account_rules(self.ascender_data))

    def test_validate_ascender_user_account_rules_new_cc(self):
        """Test the validate_ascender_user_account_rules function isn't blocked by a missing Cost Centre"""
        initial_count = CostCentre.objects.count()
        self.ascender_data["paypoint"] = "001"
        self.assertTrue(validate_ascender_user_account_rules(self.ascender_data))
        self.assertTrue(CostCentre.objects.count() > initial_count)

    def test_validate_ascender_user_account_rules_no_job_start(self):
        """Test the validate_ascender_user_account_rules function where no job start date is recorded"""
        self.ascender_data["job_start_date"] = None
        self.assertFalse(validate_ascender_user_account_rules(self.ascender_data))

    def test_validate_ascender_user_account_rules_job_start_passed(self):
        """Test the validate_ascender_user_account_rules function where a user's job start date is past"""
        last_week = date.today() - timedelta(days=7)
        self.ascender_data["job_start_date"] = last_week.strftime("%Y-%m-%d")
        self.assertFalse(validate_ascender_user_account_rules(self.ascender_data))

    def test_validate_ascender_user_account_rules_skip_job_start_passed(self):
        """Test the validate_ascender_user_account_rules function is capable of ignoring if a user's job start date is past"""
        last_week = date.today() - timedelta(days=7)
        self.ascender_data["job_start_date"] = last_week.strftime("%Y-%m-%d")
        self.assertTrue(validate_ascender_user_account_rules(self.ascender_data, ignore_job_start_date=True))

    def test_validate_ascender_user_account_rules_job_start_distant(self):
        """Test the validate_ascender_user_account_rules function where a user's job start date is too far in the future"""
        next_month = date.today() + timedelta(days=31)
        self.ascender_data["job_start_date"] = next_month.strftime("%Y-%m-%d")
        self.assertFalse(validate_ascender_user_account_rules(self.ascender_data))

    def test_validate_ascender_user_account_rules_no_physical_location(self):
        """Test the validate_ascender_user_account_rules function where a user has no physical work location recorded"""
        self.ascender_data["geo_location_desc"] = None
        self.assertFalse(validate_ascender_user_account_rules(self.ascender_data))

    def test_validate_ascender_user_account_rules_physical_location_invalid(self):
        """Test the validate_ascender_user_account_rules function where a user has a nonsense work location recorded"""
        self.ascender_data["geo_location_desc"] = "42 Everything Way, THE MOON"
        self.assertFalse(validate_ascender_user_account_rules(self.ascender_data))

    def test_generate_valid_dbca_email(self):
        """Test that generate_valid_dbca_email function works with preferred name"""
        email, mail_nickname = generate_valid_dbca_email(surname=mixer.faker.last_name(), preferred_name=mixer.faker.first_name())
        self.assertTrue(email and mail_nickname)

    def test_generate_valid_dbca_email_first_name(self):
        """Test that generate_valid_dbca_email function works with first name"""
        email, mail_nickname = generate_valid_dbca_email(surname=mixer.faker.last_name(), first_name=mixer.faker.first_name())
        self.assertTrue(email and mail_nickname)

    def test_generate_valid_dbca_email_missing_name(self):
        """Test the generate_valid_dbca_email function fails with a missing name"""
        email, mail_nickname = generate_valid_dbca_email(surname=mixer.faker.last_name())
        self.assertFalse(email and mail_nickname)

    def test_department_user_create(self):
        """Test the department_user_create function"""
        initial_count = DepartmentUser.objects.count()
        new_user = department_user_create(
            job=self.ascender_data,
            azure_guid=str(uuid4()),
            email=self.email,
            display_name=self.display_name,
            title=self.title,
            cc=self.cc,
            location=self.location,
            manager=self.manager,
        )
        self.assertTrue(isinstance(new_user, DepartmentUser))
        self.assertIsNone(new_user.position_no)
        self.assertTrue(DepartmentUser.objects.count() > initial_count)

    def test_department_user_create_position_no(self):
        """Test the department_user_create function"""
        new_user = department_user_create(
            job=self.ascender_data,
            azure_guid=str(uuid4()),
            email=self.email,
            display_name=self.display_name,
            title=self.title,
            cc=self.cc,
            location=self.location,
            manager=self.manager,
            position_no="0000000001",
        )
        self.assertEqual(new_user.position_no, "0000000001")

    def test_new_user_creation_email_sends(self):
        """Test the new_user_creation_email function"""
        new_user = self.create_new_user()
        licence_type = "On-premise"
        email_sent = new_user_creation_email(new_user, self.manager, licence_type, self.next_week)
        self.assertTrue(email_sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, f"New user account creation details - {new_user.name}")

    def test_department_user_ascender_methods(self):
        """Test the Ascender-related methods on DepartmentUser class"""
        new_user = self.create_new_user()
        self.assertTrue(new_user.get_ascender_org_path())
        self.assertTrue(new_user.get_employment_status())
        self.assertTrue(new_user.get_ascender_full_name())
        self.assertTrue(new_user.get_position_title())
        self.assertTrue(new_user.get_position_number())
        self.assertTrue(new_user.get_paypoint())
        self.assertTrue(new_user.get_ascender_clevels())
        self.assertTrue(new_user.get_geo_location_desc())
        self.assertTrue(new_user.get_job_start_date())

    def test_department_user_get_division(self):
        """Test DepartmentUser.get_division method"""
        new_user = self.create_new_user()
        self.assertTrue(new_user.get_division())
        self.assertEqual(new_user.get_division(), "Strategy and Governance")

    def test_department_user_get_business_unit(self):
        """Test DepartmentUser.get_business_unit method"""
        new_user = self.create_new_user()
        self.assertTrue(new_user.get_business_unit())
        self.assertEqual(new_user.get_business_unit(), "Office of Expectation Management")

    def test_department_user_get_term_reason(self):
        new_user = self.create_new_user()
        self.assertIsNone(new_user.get_term_reason())
        new_user.ascender_data["term_reason"] = "RE"
        new_user.save()
        self.assertTrue(new_user.get_term_reason())

    def test_sanitise_name_values(self):
        """Test the sanitise_name_values function"""
        first_name = "Joseph123"
        second_name = "O'Malley"
        surname = "Raphael Smith"
        preferred_name = "Joe-Bob"
        first_name, second_name, surname, preferred_name = sanitise_name_values(first_name, second_name, surname, preferred_name)
        self.assertEqual(first_name, "Joseph")
        self.assertEqual(second_name, "OMalley")
        self.assertEqual(surname, "RaphaelSmith")
        self.assertEqual(preferred_name, "Joe-Bob")


def _make_sku(enabled: int, warning: int, consumed: int) -> dict:
    """Return a minimal subscribedSku response dict for use in licence availability tests."""
    return {"prepaidUnits": {"enabled": enabled, "warning": warning}, "consumedUnits": consumed}


class LogAndAbortTestCase(TestCase):
    """Tests for the _log_and_abort helper."""

    def setUp(self):
        self.job = {"employee_id": "123456", "first_name": "Test", "surname": "User"}

    def test_creates_ascender_action_log_entry(self):
        """_log_and_abort creates an AscenderActionLog row with the supplied message."""
        _log_and_abort("test abort message", self.job)
        self.assertTrue(AscenderActionLog.objects.filter(log="test abort message").exists())

    def test_default_level_is_warning(self):
        """_log_and_abort defaults to WARNING level."""
        _log_and_abort("warning level test", self.job)
        log = AscenderActionLog.objects.get(log="warning level test")
        self.assertEqual(log.level, "WARNING")

    def test_custom_level_stored(self):
        """_log_and_abort stores the supplied level on the log record."""
        _log_and_abort("error level test", self.job, level="ERROR")
        log = AscenderActionLog.objects.get(log="error level test")
        self.assertEqual(log.level, "ERROR")

    def test_ascender_data_stored(self):
        """_log_and_abort persists the job dict as ascender_data on the log record."""
        _log_and_abort("data test", self.job)
        log = AscenderActionLog.objects.get(log="data test")
        self.assertEqual(log.ascender_data["employee_id"], "123456")


class SendAdminFailureEmailTestCase(TestCase):
    """Tests for the _send_admin_failure_email helper."""

    def test_email_sent_to_admin(self):
        """_send_admin_failure_email delivers one email to the configured admin address."""
        _send_admin_failure_email("Test subject", "Test body")
        self.assertEqual(len(mail.outbox), 1)

    def test_email_subject_and_body(self):
        """_send_admin_failure_email uses the supplied subject and body."""
        _send_admin_failure_email("My subject", "My body")
        msg = mail.outbox[0]
        self.assertEqual(msg.subject, "My subject")
        self.assertIn("My body", msg.body)


class ResolveNamesTestCase(TestCase):
    """Tests for the _resolve_names helper."""

    def _job(self, **overrides):
        base = {"first_name": "JOHN", "second_name": "PAUL", "surname": "SMITH", "preferred_name": "JACK"}
        base.update(overrides)
        return base

    def test_all_fields_present(self):
        first_name, second_name, surname, preferred_name = _resolve_names(self._job())
        self.assertEqual(first_name, "JOHN")
        self.assertEqual(second_name, "PAUL")
        self.assertEqual(surname, "SMITH")
        self.assertEqual(preferred_name, "JACK")

    def test_none_values_become_empty_strings(self):
        """None values in the job dict are treated as empty strings."""
        first_name, second_name, surname, preferred_name = _resolve_names(
            self._job(first_name=None, second_name=None, preferred_name=None)
        )
        self.assertEqual(first_name, "")
        self.assertEqual(second_name, "")
        self.assertEqual(preferred_name, "")

    def test_special_characters_stripped(self):
        """_resolve_names passes values through sanitise_name_values."""
        first_name, _, surname, _ = _resolve_names(self._job(first_name="O'Brien123", surname="Le Blanc"))
        self.assertEqual(first_name, "OBrien")
        self.assertEqual(surname, "LeBlanc")

    def test_hyphen_preserved(self):
        """Hyphens in names are preserved by _resolve_names."""
        _, _, _, preferred_name = _resolve_names(self._job(preferred_name="Mary-Jane"))
        self.assertEqual(preferred_name, "Mary-Jane")


class CheckLicenceAvailabilityTestCase(TestCase):
    """Tests for the _check_licence_availability helper."""

    def setUp(self):
        self.token = {"access_token": "dummy"}
        self.record = "123456, Test User"

    @patch("organisation.ascender.ms_graph_get_subscribed_sku")
    def test_onpul_available_returns_on_premise(self, mock_sku):
        """Returns 'On-premise' when E5 licence is available."""
        mock_sku.return_value = _make_sku(100, 0, 50)
        result = _check_licence_availability("ONPUL", self.token, self.record)
        self.assertEqual(result, "On-premise")

    @patch("organisation.ascender.ms_graph_get_subscribed_sku")
    def test_onpul_no_sku_data_returns_none(self, mock_sku):
        """Returns None when the E5 SKU query returns no data."""
        mock_sku.return_value = None
        result = _check_licence_availability("ONPUL", self.token, self.record)
        self.assertIsNone(result)

    @patch("organisation.ascender.ms_graph_get_subscribed_sku")
    def test_onpul_exhausted_returns_none(self, mock_sku):
        """Returns None when all E5 licences are consumed."""
        mock_sku.return_value = _make_sku(10, 0, 10)
        result = _check_licence_availability("ONPUL", self.token, self.record)
        self.assertIsNone(result)

    @patch("organisation.ascender.ms_graph_get_subscribed_sku")
    def test_cldul_all_available_returns_cloud(self, mock_sku):
        """Returns 'Cloud' when F3, Exchange Online and Security skus are available."""
        mock_sku.return_value = _make_sku(100, 0, 50)
        result = _check_licence_availability("CLDUL", self.token, self.record)
        self.assertEqual(result, "Cloud")

    @patch("organisation.ascender.ms_graph_get_subscribed_sku")
    def test_cldul_f3_no_data_returns_none(self, mock_sku):
        """Returns None when the F3 SKU query returns no data."""
        mock_sku.side_effect = [None]  # First call (F3) returns None
        result = _check_licence_availability("CLDUL", self.token, self.record)
        self.assertIsNone(result)

    @patch("organisation.ascender.ms_graph_get_subscribed_sku")
    def test_cldul_f3_exhausted_returns_none(self, mock_sku):
        """Returns None when all F3 licences are consumed."""
        mock_sku.side_effect = [_make_sku(5, 0, 5)]  # F3 exhausted
        result = _check_licence_availability("CLDUL", self.token, self.record)
        self.assertIsNone(result)

    @patch("organisation.ascender.ms_graph_get_subscribed_sku")
    def test_cldul_exchange_online_exhausted_returns_none(self, mock_sku):
        """Returns None when Exchange Online licences are exhausted."""
        mock_sku.side_effect = [_make_sku(100, 0, 50), _make_sku(5, 0, 5)]  # F3 ok, EO exhausted
        result = _check_licence_availability("CLDUL", self.token, self.record)
        self.assertIsNone(result)

    @patch("organisation.ascender.ms_graph_get_subscribed_sku")
    def test_cldul_security_addon_exhausted_returns_none(self, mock_sku):
        """Returns None when Security + Compliance Add-on licences are exhausted."""
        mock_sku.side_effect = [_make_sku(100, 0, 50), _make_sku(100, 0, 50), _make_sku(5, 0, 5)]
        result = _check_licence_availability("CLDUL", self.token, self.record)
        self.assertIsNone(result)

    @patch("organisation.ascender.ms_graph_get_subscribed_sku")
    def test_invalid_licence_code_returns_none(self, mock_sku):
        """Returns None for an unrecognised licence type code."""
        result = _check_licence_availability("FOOBAR", self.token, self.record)
        self.assertIsNone(result)
        mock_sku.assert_not_called()

    @patch("organisation.ascender.ms_graph_get_subscribed_sku")
    def test_onpul_available_with_warning_units(self, mock_sku):
        """Licence availability calculation includes 'warning' prepaid units."""
        # 8 enabled + 2 warning = 10 assignable; 9 consumed → 1 available
        mock_sku.return_value = _make_sku(8, 2, 9)
        result = _check_licence_availability("ONPUL", self.token, self.record)
        self.assertEqual(result, "On-premise")


class BuildLicencePayloadTestCase(TestCase):
    """Tests for the _build_licence_payload helper."""

    def test_on_premise_payload_contains_e5(self):
        """On-premise payload assigns exactly one licence: Microsoft 365 E5."""
        payload = _build_licence_payload("On-premise")
        skus = [item["skuId"] for item in payload["addLicenses"]]
        self.assertIn(MS_PRODUCTS["MICROSOFT 365 E5"], skus)
        self.assertEqual(len(payload["addLicenses"]), 1)

    def test_on_premise_no_disabled_plans(self):
        """On-premise E5 licence has no disabled plans."""
        payload = _build_licence_payload("On-premise")
        self.assertEqual(payload["addLicenses"][0]["disabledPlans"], [])

    def test_cloud_payload_contains_three_skus(self):
        """Cloud payload assigns F3, Exchange Online Plan 2, and the Security Add-on."""
        payload = _build_licence_payload("Cloud")
        skus = [item["skuId"] for item in payload["addLicenses"]]
        self.assertIn(MS_PRODUCTS["MICROSOFT 365 F3"], skus)
        self.assertIn(MS_PRODUCTS["EXCHANGE ONLINE (PLAN 2)"], skus)
        self.assertIn(MS_PRODUCTS["MICROSOFT 365 F5 SECURITY + COMPLIANCE ADD-ON"], skus)
        self.assertEqual(len(payload["addLicenses"]), 3)

    def test_cloud_f3_disables_exchange_online_kiosk(self):
        """Cloud F3 licence disables Exchange Online Kiosk plan."""
        payload = _build_licence_payload("Cloud")
        f3 = next(item for item in payload["addLicenses"] if item["skuId"] == MS_PRODUCTS["MICROSOFT 365 F3"])
        self.assertIn(MS_PRODUCTS["EXCHANGE ONLINE KIOSK"], f3["disabledPlans"])

    def test_remove_licences_always_empty(self):
        """removeLicenses list is always empty in the payload."""
        self.assertEqual(_build_licence_payload("On-premise")["removeLicenses"], [])
        self.assertEqual(_build_licence_payload("Cloud")["removeLicenses"], [])


class WaitForUsageLocationTestCase(TestCase):
    """Tests for the _wait_for_usage_location helper."""

    def setUp(self):
        self.guid = str(uuid4())
        self.headers = {"Authorization": "Bearer dummy"}
        self.job = {"employee_id": "123456", "first_name": "Test", "surname": "User"}
        self.email = "test.user@dbca.wa.gov.au"

    @patch("organisation.ascender.sleep")
    @patch("organisation.ascender.requests.get")
    def test_returns_true_when_usage_location_set(self, mock_get, mock_sleep):
        """Returns True immediately when usageLocation is 'AU' on the first poll."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": self.guid, "usageLocation": "AU"}
        mock_get.return_value = mock_resp
        result = _wait_for_usage_location(self.guid, self.headers, self.job, self.email)
        self.assertTrue(result)
        mock_sleep.assert_not_called()

    @patch("organisation.ascender.sleep")
    @patch("organisation.ascender.requests.get")
    def test_returns_false_on_timeout_and_logs(self, mock_get, mock_sleep):
        """Returns False and creates an AscenderActionLog when usageLocation never appears."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": self.guid, "usageLocation": None}
        mock_get.return_value = mock_resp
        result = _wait_for_usage_location(self.guid, self.headers, self.job, self.email)
        self.assertFalse(result)
        self.assertTrue(AscenderActionLog.objects.filter(log__icontains="usageLocation field value not set").exists())

    @patch("organisation.ascender.sleep")
    @patch("organisation.ascender.requests.get")
    def test_returns_false_on_timeout_sends_email(self, mock_get, mock_sleep):
        """Sends an admin alert email when the usageLocation poll times out."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": self.guid}  # no usageLocation key
        mock_get.return_value = mock_resp
        _wait_for_usage_location(self.guid, self.headers, self.job, self.email)
        self.assertGreater(len(mail.outbox), 0)

    @patch("organisation.ascender.sleep")
    @patch("organisation.ascender.requests.get")
    def test_returns_true_after_initial_failures(self, mock_get, mock_sleep):
        """Returns True once the poll eventually sees usageLocation == 'AU'."""
        resp_no_location = MagicMock()
        resp_no_location.json.return_value = {"id": self.guid}
        resp_with_location = MagicMock()
        resp_with_location.json.return_value = {"id": self.guid, "usageLocation": "AU"}
        mock_get.side_effect = [resp_no_location, resp_no_location, resp_with_location]
        result = _wait_for_usage_location(self.guid, self.headers, self.job, self.email)
        self.assertTrue(result)


class AssignLicenceWithRetryTestCase(TestCase):
    """Tests for the _assign_licence_with_retry helper."""

    def setUp(self):
        self.guid = str(uuid4())
        self.headers = {"Authorization": "Bearer dummy"}
        self.job = {"employee_id": "123456", "first_name": "Test", "surname": "User"}
        self.email = "test.user@dbca.wa.gov.au"
        self.payload = {"addLicenses": [], "removeLicenses": []}

    @patch("organisation.ascender.sleep")
    @patch("organisation.ascender.requests.post")
    def test_returns_true_on_success(self, mock_post, mock_sleep):
        """Returns True when the licence assignment POST succeeds on the first attempt."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp
        result = _assign_licence_with_retry(self.guid, self.headers, self.payload, self.job, self.email, "123456, Test User")
        self.assertTrue(result)

    @patch("organisation.ascender.sleep")
    @patch("organisation.ascender.requests.delete")
    @patch("organisation.ascender.requests.post")
    def test_returns_false_on_timeout_and_logs(self, mock_post, mock_delete, mock_sleep):
        """Returns False and creates a log entry when licence assignment exhausts retries."""
        import requests as req

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req.exceptions.HTTPError("500")
        mock_post.return_value = mock_resp
        mock_delete.return_value = MagicMock()
        result = _assign_licence_with_retry(self.guid, self.headers, self.payload, self.job, self.email, "123456, Test User")
        self.assertFalse(result)
        self.assertTrue(AscenderActionLog.objects.filter(log__icontains="assign license step").exists())

    @patch("organisation.ascender.sleep")
    @patch("organisation.ascender.requests.delete")
    @patch("organisation.ascender.requests.post")
    def test_deletes_orphan_on_failure(self, mock_post, mock_delete, mock_sleep):
        """Attempts to delete the orphaned Entra ID account when licence assignment fails."""
        import requests as req

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req.exceptions.HTTPError("500")
        mock_post.return_value = mock_resp
        mock_delete_resp = MagicMock()
        mock_delete.return_value = mock_delete_resp
        _assign_licence_with_retry(self.guid, self.headers, self.payload, self.job, self.email, "123456, Test User")
        mock_delete.assert_called_once()
        url_called = mock_delete.call_args[0][0]
        self.assertIn(self.guid, url_called)

    @patch("organisation.ascender.sleep")
    @patch("organisation.ascender.requests.delete")
    @patch("organisation.ascender.requests.post")
    def test_logs_cleanup_failure(self, mock_post, mock_delete, mock_sleep):
        """Logs a WARNING when the orphan deletion itself fails."""
        import requests as req

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req.exceptions.HTTPError("500")
        mock_post.return_value = mock_resp
        mock_delete_resp = MagicMock()
        mock_delete_resp.raise_for_status.side_effect = req.exceptions.HTTPError("404")
        mock_delete.return_value = mock_delete_resp
        _assign_licence_with_retry(self.guid, self.headers, self.payload, self.job, self.email, "123456, Test User")
        self.assertTrue(AscenderActionLog.objects.filter(log__icontains="manual deletion required").exists())

    @patch("organisation.ascender.sleep")
    @patch("organisation.ascender.requests.delete")
    @patch("organisation.ascender.requests.post")
    def test_returns_false_and_sends_email_on_failure(self, mock_post, mock_delete, mock_sleep):
        """Sends an admin alert email when licence assignment exhausts retries."""
        import requests as req

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req.exceptions.HTTPError("500")
        mock_post.return_value = mock_resp
        mock_delete.return_value = MagicMock()
        _assign_licence_with_retry(self.guid, self.headers, self.payload, self.job, self.email, "123456, Test User")
        self.assertGreater(len(mail.outbox), 0)


class CreateEntraIdUserTestCase(TestCase):
    """Tests for the create_entra_id_user coordinator function.

    Tests focus on the pre-flight validation paths that do not require live Graph API
    calls, using settings overrides and mocks to exercise each early-exit branch.
    """

    def setUp(self):
        loc_desc = "1 Fake Street, DULLSVILLE"
        self.location = mixer.blend(Location, name=loc_desc, ascender_desc=loc_desc)
        cc_code = str(random.randint(100, 999))
        self.cc = mixer.blend(CostCentre, code=cc_code, ascender_code=cc_code)
        self.manager = mixer.blend(
            DepartmentUser,
            active=True,
            email=random_dbca_email,
            given_name=mixer.RANDOM,
            surname=mixer.RANDOM,
            azure_guid=str(uuid4()),
            employee_id=str(random.randint(100000, 999999)),
        )
        self.next_week = date.today() + timedelta(days=7)
        self.job = {
            "employee_id": str(random.randint(100000, 999999)),
            "first_name": "JOHN",
            "second_name": "PAUL",
            "surname": "SMITH",
            "preferred_name": None,
            "occup_pos_title": "SENIOR RANGER",
            "job_end_date": None,
            "licence_type": "ONPUL",
            "manager_emp_no": str(self.manager.employee_id),
        }
        self.token = {"access_token": "dummy-token"}

    def test_returns_none_if_manager_has_no_azure_guid(self):
        """Returns None when the manager does not have an Entra ID account."""
        self.manager.azure_guid = None
        self.manager.save()
        result = create_entra_id_user(self.job, self.cc, self.next_week, self.manager, self.location, token=self.token)
        self.assertIsNone(result)

    def test_returns_none_if_surname_absent(self):
        """Returns None and creates an AscenderActionLog entry when surname is missing."""
        self.job["surname"] = None
        with patch("organisation.ascender._check_licence_availability", return_value="On-premise"):
            result = create_entra_id_user(self.job, self.cc, self.next_week, self.manager, self.location, token=self.token)
        self.assertIsNone(result)
        self.assertTrue(AscenderActionLog.objects.filter(log__icontains="surname absent").exists())

    def test_returns_none_if_first_and_preferred_name_absent(self):
        """Returns None when both first_name and preferred_name are absent."""
        self.job["first_name"] = None
        self.job["preferred_name"] = None
        with patch("organisation.ascender._check_licence_availability", return_value="On-premise"):
            result = create_entra_id_user(self.job, self.cc, self.next_week, self.manager, self.location, token=self.token)
        self.assertIsNone(result)
        self.assertTrue(AscenderActionLog.objects.filter(log__icontains="first and preferred name both absent").exists())

    @patch("organisation.ascender._check_licence_availability", return_value=None)
    def test_returns_none_if_licence_check_fails(self, mock_licence):
        """Returns None when _check_licence_availability returns None."""
        result = create_entra_id_user(self.job, self.cc, self.next_week, self.manager, self.location, token=self.token)
        self.assertIsNone(result)

    @patch("organisation.ascender.ms_graph_validate_password", return_value=True)
    @patch("organisation.ascender._check_licence_availability", return_value="On-premise")
    @override_settings(ASCENDER_CREATE_AZURE_AD=False, DEBUG=False)
    def test_returns_none_when_create_azure_ad_disabled(self, mock_licence, mock_pwd):
        """Returns None (without calling Graph API) when ASCENDER_CREATE_AZURE_AD is False."""
        result = create_entra_id_user(self.job, self.cc, self.next_week, self.manager, self.location, token=self.token)
        self.assertIsNone(result)

    @patch("organisation.ascender.ms_graph_validate_password", return_value=True)
    @patch("organisation.ascender._check_licence_availability", return_value="On-premise")
    @override_settings(ASCENDER_CREATE_AZURE_AD=True, DEBUG=True)
    def test_returns_none_in_debug_mode(self, mock_licence, mock_pwd):
        """Returns None (without calling Graph API) when DEBUG is True."""
        result = create_entra_id_user(self.job, self.cc, self.next_week, self.manager, self.location, token=self.token)
        self.assertIsNone(result)

    @patch("organisation.ascender._check_licence_availability", return_value="On-premise")
    def test_email_generation_failure_returns_none_with_log(self, mock_licence):
        """Returns None and logs when a unique email address cannot be generated."""
        with patch("organisation.ascender.generate_valid_dbca_email", return_value=(None, None)):
            result = create_entra_id_user(self.job, self.cc, self.next_week, self.manager, self.location, token=self.token)
        self.assertIsNone(result)
        self.assertTrue(AscenderActionLog.objects.filter(log__icontains="unable to generate unique email").exists())
