import re

from django.test import TestCase

from organisation.utils import generate_password, title_except


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
        self.assertEqual(
            title_except("A/SENIOR CONSERVATION OFFICER (Planning and Operations)"),
            "A/Senior Conservation Officer (Planning and Operations)",
        )
