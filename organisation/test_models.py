import logging
import random
import string
from uuid import uuid1

from django.test import TestCase
from django.utils import timezone
from mixer.backend.django import mixer

from itassets.test_api import random_dbca_email
from organisation.models import CostCentre, DepartmentUser

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
            shared_account=False,
            dir_sync_enabled=True,
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
        self.user.save()
        self.manager = mixer.blend(
            DepartmentUser,
            active=True,
            email=random_dbca_email,
            given_name=mixer.RANDOM,
            surname=mixer.RANDOM,
            employee_id=mixer.RANDOM,
            shared_account=False,
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
        self.assertFalse(self.user.shared_account)
        self.user.employee_id = "N/A"
        self.user.account_type = 5
        self.user.save()
        self.assertFalse(self.user.employee_id)
        self.assertTrue(self.user.shared_account)

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
        self.assertEqual(self.user.get_ascender_full_name(), "JANEY DOE")

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
