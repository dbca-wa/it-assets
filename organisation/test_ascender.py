import random
from datetime import date, timedelta
from uuid import uuid4

from django.core import mail
from django.test import TestCase
from mixer.backend.django import mixer

from itassets.test_api import random_dbca_email
from organisation.ascender import (
    check_ascender_user_account_rules,
    department_user_create,
    generate_valid_dbca_email,
    new_user_creation_email,
)
from organisation.models import CostCentre, DepartmentUser, Location
from organisation.utils import title_except


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
        self.ascender_data_valid = {
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
            "emp_status": "PFA",
            "position_no": str(random.randint(10000000, 99999999)),
            "job_start_date": self.next_week.strftime("%Y-%m-%d"),
            "job_end_date": None,
            "licence_type": "ONPUL",
            "manager_emp_no": str(self.manager.employee_id),
        }

    def test_check_ascender_user_account_rules(self):
        self.assertTrue(check_ascender_user_account_rules(self.ascender_data_valid))

    def test_check_ascender_user_account_rules_fpc(self):
        self.ascender_data_valid["clevel1_id"] = "FPC"
        self.assertFalse(check_ascender_user_account_rules(self.ascender_data_valid))

    def test_check_ascender_user_account_rules_user_exists(self):
        mixer.blend(
            DepartmentUser,
            active=True,
            email=random_dbca_email,
            given_name=mixer.RANDOM,
            surname=mixer.RANDOM,
            employee_id=self.ascender_data_valid["employee_id"],
        )
        self.assertFalse(check_ascender_user_account_rules(self.ascender_data_valid))

    def test_check_ascender_user_account_rules_job_ended(self):
        last_week = date.today() - timedelta(days=7)
        self.ascender_data_valid["job_end_date"] = last_week.strftime("%Y-%m-%d")
        self.assertFalse(check_ascender_user_account_rules(self.ascender_data_valid))

    def test_check_ascender_user_account_rules_no_licence(self):
        self.ascender_data_valid["licence_type"] = None
        self.assertFalse(check_ascender_user_account_rules(self.ascender_data_valid))

    def test_check_ascender_user_account_rules_licence_invalid(self):
        self.ascender_data_valid["licence_type"] = "FOOBAR"
        self.assertFalse(check_ascender_user_account_rules(self.ascender_data_valid))

    def test_check_ascender_user_account_rules_no_manager(self):
        self.ascender_data_valid["manager_emp_no"] = None
        self.assertFalse(check_ascender_user_account_rules(self.ascender_data_valid))
        self.ascender_data_valid["manager_emp_no"] = "000001"
        self.assertFalse(check_ascender_user_account_rules(self.ascender_data_valid))

    def test_check_ascender_user_account_rules_new_cc(self):
        initial_count = CostCentre.objects.count()
        self.ascender_data_valid["paypoint"] = "001"
        self.assertTrue(check_ascender_user_account_rules(self.ascender_data_valid))
        self.assertTrue(CostCentre.objects.count() > initial_count)

    def test_check_ascender_user_account_rules_no_job_start(self):
        self.ascender_data_valid["job_start_date"] = None
        self.assertFalse(check_ascender_user_account_rules(self.ascender_data_valid))

    def test_check_ascender_user_account_rules_job_start_passed(self):
        last_week = date.today() - timedelta(days=7)
        self.ascender_data_valid["job_start_date"] = last_week.strftime("%Y-%m-%d")
        self.assertFalse(check_ascender_user_account_rules(self.ascender_data_valid))

    def test_check_ascender_user_account_rules_skip_job_start_passed(self):
        last_week = date.today() - timedelta(days=7)
        self.ascender_data_valid["job_start_date"] = last_week.strftime("%Y-%m-%d")
        self.assertTrue(check_ascender_user_account_rules(self.ascender_data_valid, ignore_job_start_date=True))

    def test_check_ascender_user_account_rules_job_start_distant(self):
        next_month = date.today() + timedelta(days=31)
        self.ascender_data_valid["job_start_date"] = next_month.strftime("%Y-%m-%d")
        self.assertFalse(check_ascender_user_account_rules(self.ascender_data_valid))

    def test_check_ascender_user_account_rules_no_physical_location(self):
        self.ascender_data_valid["geo_location_desc"] = None
        self.assertFalse(check_ascender_user_account_rules(self.ascender_data_valid))

    def test_check_ascender_user_account_rules_physical_location_invalid(self):
        self.ascender_data_valid["geo_location_desc"] = "42 Everything Way, THE MOON"
        self.assertFalse(check_ascender_user_account_rules(self.ascender_data_valid))

    def test_generate_valid_dbca_email(self):
        email, mail_nickname = generate_valid_dbca_email(
            surname=mixer.faker.last_name(), preferred_name=mixer.faker.first_name()
        )
        self.assertTrue(email and mail_nickname)

    def test_generate_valid_dbca_email_first_name(self):
        email, mail_nickname = generate_valid_dbca_email(
            surname=mixer.faker.last_name(), first_name=mixer.faker.first_name()
        )
        self.assertTrue(email and mail_nickname)

    def test_generate_valid_dbca_email_missing_name(self):
        email, mail_nickname = generate_valid_dbca_email(surname=mixer.faker.last_name())
        self.assertFalse(email and mail_nickname)

    def test_department_user_create(self):
        email, _ = generate_valid_dbca_email(
            surname=self.ascender_data_valid["surname"], first_name=self.ascender_data_valid["first_name"]
        )
        display_name = f"{self.ascender_data_valid['first_name'].title().strip()} {self.ascender_data_valid['surname'].title().strip()}"
        title = title_except(self.ascender_data_valid["occup_pos_title"])
        initial_count = DepartmentUser.objects.count()
        self.assertTrue(
            department_user_create(
                job=self.ascender_data_valid,
                guid=str(uuid4()),
                email=email,
                display_name=display_name,
                title=title,
                cc=self.cc,
                location=self.location,
                manager=self.manager,
            )
        )
        self.assertTrue(DepartmentUser.objects.count() > initial_count)

    def test_new_user_creation_email_sends(self):
        email, _ = generate_valid_dbca_email(
            surname=self.ascender_data_valid["surname"], first_name=self.ascender_data_valid["first_name"]
        )
        display_name = f"{self.ascender_data_valid['first_name'].title().strip()} {self.ascender_data_valid['surname'].title().strip()}"
        title = title_except(self.ascender_data_valid["occup_pos_title"])
        new_user = department_user_create(
            job=self.ascender_data_valid,
            guid=str(uuid4()),
            email=email,
            display_name=display_name,
            title=title,
            cc=self.cc,
            location=self.location,
            manager=self.manager,
        )
        licence_type = "On-premise"
        new_user_creation_email(new_user, licence_type, job_start_date=self.next_week)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, f"New user account creation details - {new_user.name}")
