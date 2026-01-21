import logging
import random
from datetime import date, timedelta
from uuid import uuid4

from django.core import mail
from django.test import TestCase
from mixer.backend.django import mixer

from itassets.test_api import random_dbca_email
from organisation.ascender import (
    department_user_create,
    generate_valid_dbca_email,
    new_user_creation_email,
    sanitise_name_values,
    validate_ascender_user_account_rules,
)
from organisation.models import CostCentre, DepartmentUser, Location
from organisation.utils import title_except

# Disable non-critical logging output.
logging.disable(logging.CRITICAL)


class AscenderTestCase(TestCase):
    """Test functions related to the import of department user data from Ascender."""

    def setUp(self):
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
