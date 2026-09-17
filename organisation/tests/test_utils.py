import os
import re
from datetime import datetime
from unittest.mock import MagicMock, patch

from django.test import TestCase

from organisation.utils import (
    compare_values,
    generate_password,
    ms_graph_get_subscribed_sku,
    ms_graph_get_user,
    ms_graph_list_signins_user,
    ms_graph_list_subscribed_skus,
    ms_graph_list_users,
    ms_graph_validate_password,
    ms_graph_list_member_groups_with_names,
    parse_ad_pwd_last_set,
    parse_windows_ts,
    title_except,
)


class UtilsTest(TestCase):
    def test_generate_password(self):
        """Test that our generated password meets complexity requirements."""
        password = generate_password()
        self.assertTrue(len(password) >= 16)
        self.assertTrue(re.search(r"[A-Z]", password))
        self.assertTrue(re.search(r"[a-z]", password))
        self.assertTrue(re.search(r"\d", password))

    def test_title_except(self):
        """Test the title_except utility function returns title in expected casing."""
        self.assertEqual(title_except("MANAGER"), "Manager")
        self.assertEqual(title_except("manager"), "Manager")
        self.assertEqual(title_except("A/MANAGER"), "A/Manager")
        self.assertEqual(title_except("MANAGER OIM"), "Manager OIM")
        self.assertEqual(title_except("MANAGER, AUDIT AND RISK"), "Manager, Audit and Risk")
        self.assertEqual(title_except("A/OIM COORDINATOR"), "A/OIM Coordinator")
        self.assertEqual(
            title_except("A/SENIOR CONSERVATION OFFICER (Planning and Operations)"),
            "A/Senior Conservation Officer (Planning and Operations)",
        )


FAKE_TOKEN = {"token_type": "Bearer", "access_token": "fake-access-token"}
AZURE_TENANT_ENV = {"AZURE_TENANT_ID": "test-tenant-id"}


def mock_response(data, status_code=200):
    """Return a mock requests.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    return resp


def make_graph_user(**overrides):
    """Return a minimal Graph API user dict as returned by /users."""
    base = {
        "id": "aaaaaaaa-0000-0000-0000-000000000001",
        "mail": "Jane.Smith@Example.com",
        "userPrincipalName": "Jane.Smith@Example.com",
        "displayName": "Jane Smith",
        "givenName": "Jane",
        "surname": "Smith",
        "employeeId": "12345",
        "employeeType": "Employee",
        "jobTitle": "Developer",
        "businessPhones": ["08 9999 0001"],
        "mobilePhone": "0400 000 001",
        "department": "IT",
        "companyName": "001",
        "officeLocation": "Perth",
        "proxyAddresses": ["SMTP:Jane.Smith@Example.com", "smtp:alias@example.com"],
        "accountEnabled": True,
        "onPremisesSyncEnabled": True,
        "onPremisesSamAccountName": "jsmith",
        "lastPasswordChangeDateTime": "2024-06-01T00:00:00Z",
        "createdDateTime": "2023-01-01T00:00:00Z",
        "assignedLicenses": [{"skuId": "sku-abc-123"}],
    }
    base.update(overrides)
    return base


class CompareValuesTestCase(TestCase):
    def test_both_none(self):
        self.assertTrue(compare_values(None, None))

    def test_both_empty_string(self):
        self.assertTrue(compare_values("", ""))

    def test_none_and_empty_string(self):
        self.assertTrue(compare_values(None, ""))
        self.assertTrue(compare_values("", None))

    def test_equal_values(self):
        self.assertTrue(compare_values("hello", "hello"))
        self.assertTrue(compare_values(42, 42))

    def test_unequal_values(self):
        self.assertFalse(compare_values("hello", "world"))
        self.assertFalse(compare_values("value", None))
        self.assertFalse(compare_values(None, "value"))


class ParseWindowsTsTestCase(TestCase):
    def test_valid_timestamp(self):
        # A known Windows timestamp string (milliseconds since epoch, embedded in a string).
        # 1700000000000 ms = 2023-11-14 22:13:20 UTC
        result = parse_windows_ts("1700000000000")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, datetime)

    def test_timestamp_in_longer_string(self):
        result = parse_windows_ts("ts=1700000000000 other stuff")
        self.assertIsNotNone(result)

    def test_invalid_returns_none(self):
        result = parse_windows_ts("no-numbers-here-at-all")
        self.assertIsNone(result)

    def test_empty_string_returns_none(self):
        result = parse_windows_ts("")
        self.assertIsNone(result)


class ParseAdPwdLastSetTestCase(TestCase):
    def test_returns_datetime(self):
        # Pwd-Last-Set value for a known date.
        # Windows epoch is 1601-01-01; 100ns intervals.
        # Calculate a value for 2024-01-01 00:00:00 UTC:
        # (2024-01-01 - 1601-01-01) = 153375 days
        days = (datetime(2024, 1, 1) - datetime(1601, 1, 1)).days
        pwd_last_set = days * 24 * 60 * 60 * 10_000_000  # in 100ns intervals
        result = parse_ad_pwd_last_set(pwd_last_set)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 1)


class MsGraphListSubscribedSkusTestCase(TestCase):
    @patch("organisation.utils.requests.get")
    def test_single_page(self, mock_get):
        skus = [{"skuId": "sku-001", "skuPartNumber": "M365_E5"}]
        mock_get.return_value = mock_response({"value": skus})

        result = ms_graph_list_subscribed_skus(token=FAKE_TOKEN)

        self.assertEqual(result, skus)
        mock_get.assert_called_once()

    @patch("organisation.utils.requests.get")
    def test_paginated_results(self, mock_get):
        page1 = {"value": [{"skuId": "sku-001"}], "@odata.nextLink": "https://graph.microsoft.com/next"}
        page2 = {"value": [{"skuId": "sku-002"}]}
        mock_get.side_effect = [mock_response(page1), mock_response(page2)]

        result = ms_graph_list_subscribed_skus(token=FAKE_TOKEN)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["skuId"], "sku-001")
        self.assertEqual(result[1]["skuId"], "sku-002")
        self.assertEqual(mock_get.call_count, 2)

    @patch("organisation.utils.ms_graph_client_token")
    def test_returns_none_when_token_fails(self, mock_token):
        mock_token.return_value = None

        result = ms_graph_list_subscribed_skus()

        self.assertIsNone(result)


class MsGraphGetSubscribedSkuTestCase(TestCase):
    @patch.dict(os.environ, AZURE_TENANT_ENV)
    @patch("organisation.utils.requests.get")
    def test_returns_sku_data(self, mock_get):
        sku_data = {"skuId": "sku-001", "consumedUnits": 10, "prepaidUnits": {"enabled": 100, "warning": 0}}
        mock_get.return_value = mock_response(sku_data)

        result = ms_graph_get_subscribed_sku("sku-001", token=FAKE_TOKEN)

        self.assertEqual(result, sku_data)
        called_url = mock_get.call_args[0][0]
        self.assertIn("test-tenant-id_sku-001", called_url)

    @patch("organisation.utils.ms_graph_client_token")
    def test_returns_none_when_token_fails(self, mock_token):
        mock_token.return_value = None

        result = ms_graph_get_subscribed_sku("sku-001")

        self.assertIsNone(result)


class MsGraphListUsersTestCase(TestCase):
    @patch("organisation.utils.requests.get")
    def test_returns_transformed_users(self, mock_get):
        user = make_graph_user()
        mock_get.return_value = mock_response({"value": [user]})

        result = ms_graph_list_users(token=FAKE_TOKEN)

        self.assertEqual(len(result), 1)
        u = result[0]
        # UPN and mail should be lowercased.
        self.assertEqual(u["userPrincipalName"], "jane.smith@example.com")
        self.assertEqual(u["mail"], "jane.smith@example.com")
        # proxyAddresses strips "smtp:" prefix and lowercases.
        self.assertIn("jane.smith@example.com", u["proxyAddresses"])
        self.assertIn("alias@example.com", u["proxyAddresses"])
        # assignedLicenses maps to skuId list.
        self.assertEqual(u["assignedLicenses"], ["sku-abc-123"])

    @patch("organisation.utils.requests.get")
    def test_user_without_manager(self, mock_get):
        user = make_graph_user()
        # Graph API omits the "manager" key when not set.
        mock_get.return_value = mock_response({"value": [user]})

        result = ms_graph_list_users(token=FAKE_TOKEN)

        self.assertIsNone(result[0]["manager"])

    @patch("organisation.utils.requests.get")
    def test_user_with_manager(self, mock_get):
        user = make_graph_user()
        user["manager"] = {"id": "mgr-guid", "mail": "manager@example.com"}
        mock_get.return_value = mock_response({"value": [user]})

        result = ms_graph_list_users(token=FAKE_TOKEN)

        self.assertEqual(result[0]["manager"], {"id": "mgr-guid", "mail": "manager@example.com"})

    @patch("organisation.utils.requests.get")
    def test_paginated_results(self, mock_get):
        user1 = make_graph_user(id="guid-001", mail="a@example.com", userPrincipalName="a@example.com")
        user2 = make_graph_user(id="guid-002", mail="b@example.com", userPrincipalName="b@example.com")
        page1 = {"value": [user1], "@odata.nextLink": "https://graph.microsoft.com/next"}
        page2 = {"value": [user2]}
        mock_get.side_effect = [mock_response(page1), mock_response(page2)]

        result = ms_graph_list_users(token=FAKE_TOKEN)

        self.assertEqual(len(result), 2)

    @patch("organisation.utils.requests.get")
    def test_licensed_filter(self, mock_get):
        licensed_user = make_graph_user(
            id="guid-001", mail="a@example.com", userPrincipalName="a@example.com", assignedLicenses=[{"skuId": "sku-1"}]
        )
        unlicensed_user = make_graph_user(id="guid-002", mail="b@example.com", userPrincipalName="b@example.com", assignedLicenses=[])
        mock_get.return_value = mock_response({"value": [licensed_user, unlicensed_user]})

        result = ms_graph_list_users(licensed=True, token=FAKE_TOKEN)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["objectId"], "guid-001")

    @patch("organisation.utils.requests.get")
    def test_no_filter_returns_all(self, mock_get):
        licensed_user = make_graph_user(
            id="guid-001", mail="a@example.com", userPrincipalName="a@example.com", assignedLicenses=[{"skuId": "sku-1"}]
        )
        unlicensed_user = make_graph_user(id="guid-002", mail="b@example.com", userPrincipalName="b@example.com", assignedLicenses=[])
        mock_get.return_value = mock_response({"value": [licensed_user, unlicensed_user]})

        result = ms_graph_list_users(licensed=False, token=FAKE_TOKEN)

        self.assertEqual(len(result), 2)

    @patch("organisation.utils.ms_graph_client_token")
    def test_returns_none_when_token_fails(self, mock_token):
        mock_token.return_value = None

        result = ms_graph_list_users()

        self.assertIsNone(result)

    @patch("organisation.utils.requests.get")
    def test_null_fields_become_none(self, mock_get):
        user = make_graph_user(
            mail=None,
            displayName=None,
            givenName=None,
            surname=None,
            employeeId=None,
            employeeType=None,
            jobTitle=None,
            businessPhones=[],
            mobilePhone=None,
            department=None,
            companyName=None,
            officeLocation=None,
        )
        mock_get.return_value = mock_response({"value": [user]})

        result = ms_graph_list_users(token=FAKE_TOKEN)

        u = result[0]
        self.assertIsNone(u["mail"])
        self.assertIsNone(u["displayName"])
        self.assertIsNone(u["telephoneNumber"])


class MsGraphGetUserTestCase(TestCase):
    @patch("organisation.utils.requests.get")
    def test_returns_user_data(self, mock_get):
        user_data = make_graph_user()
        mock_get.return_value = mock_response(user_data)

        result = ms_graph_get_user("some-guid", token=FAKE_TOKEN)

        self.assertEqual(result, user_data)
        called_url = mock_get.call_args[0][0]
        self.assertIn("some-guid", called_url)

    @patch("organisation.utils.ms_graph_client_token")
    def test_returns_none_when_token_fails(self, mock_token):
        mock_token.return_value = None

        result = ms_graph_get_user("some-guid")

        self.assertIsNone(result)


class MsGraphValidatePasswordTestCase(TestCase):
    @patch("organisation.utils.requests.post")
    def test_valid_password(self, mock_post):
        mock_post.return_value = mock_response({"isValid": True})

        result = ms_graph_validate_password("Str0ng!Pass", token=FAKE_TOKEN)

        self.assertTrue(result)
        called_url = mock_post.call_args[0][0]
        self.assertIn("validatePassword", called_url)

    @patch("organisation.utils.requests.post")
    def test_invalid_password(self, mock_post):
        mock_post.return_value = mock_response({"isValid": False})

        result = ms_graph_validate_password("weak", token=FAKE_TOKEN)

        self.assertFalse(result)

    @patch("organisation.utils.ms_graph_client_token")
    def test_returns_none_when_token_fails(self, mock_token):
        mock_token.return_value = None

        result = ms_graph_validate_password("anypassword")

        self.assertIsNone(result)


class MsGraphListSigninsUserTestCase(TestCase):
    @patch("organisation.utils.requests.get")
    def test_returns_signins(self, mock_get):
        signins = [
            {"id": "signin-001", "createdDateTime": "2024-06-01T10:00:00Z", "isInteractive": True},
            {"id": "signin-002", "createdDateTime": "2024-05-30T08:00:00Z", "isInteractive": True},
        ]
        mock_get.return_value = mock_response({"value": signins})

        result = ms_graph_list_signins_user("user-guid-001", token=FAKE_TOKEN)

        self.assertEqual(result, signins)
        called_url = mock_get.call_args[0][0]
        self.assertIn("signIns", called_url)

    @patch("organisation.utils.requests.get")
    def test_passes_top_parameter(self, mock_get):
        mock_get.return_value = mock_response({"value": []})

        ms_graph_list_signins_user("user-guid-001", top=10, token=FAKE_TOKEN)

        params = mock_get.call_args[1]["params"]
        self.assertEqual(params["$top"], 10)

    @patch("organisation.utils.requests.get")
    def test_filters_by_user_guid(self, mock_get):
        mock_get.return_value = mock_response({"value": []})

        ms_graph_list_signins_user("user-guid-001", token=FAKE_TOKEN)

        params = mock_get.call_args[1]["params"]
        self.assertIn("user-guid-001", params["$filter"])

    @patch("organisation.utils.ms_graph_client_token")
    def test_returns_none_when_token_fails(self, mock_token):
        mock_token.return_value = None

        result = ms_graph_list_signins_user("user-guid-001")

        self.assertIsNone(result)


class MsGraphListMemberGroupsWithNamesTestCase(TestCase):
    @patch("organisation.utils.requests.get")
    def test_ms_graph_list_member_groups_with_names(self, mock_get):
        package = {
            "value": [
                {"@odata.type": "#microsoft.graph.group", "id": "sku-1", "displayName": "example-group-1"},
                {"@odata.type": "#microsoft.graph.group", "id": "sku-2", "displayName": "example-group-2"},
            ]
        }
        mock_get.return_value = mock_response(package)

        result = ms_graph_list_member_groups_with_names(token=FAKE_TOKEN, azure_guid="some guid")

        self.assertEqual(result["example-group-1"], "sku-1")
        self.assertEqual(result["example-group-2"], "sku-2")
        self.assertEqual(len(result), 2)
