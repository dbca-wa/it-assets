import logging
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from mixer.backend.django import mixer

from organisation.management.commands.department_users_terminated_users_handling import Command
from organisation.management.commands.organisation_generate_dummy_data import DIVISION_NAMES, EMP_STATUS
from organisation.models import CostCentre, DepartmentUser, Location

# Disable non-critical logging output.
logging.disable(logging.CRITICAL)


class TerminatedUsersTestCase(TestCase):
    def setUp(self) -> None:
        # 1 user not-term, 1 user term, 1 user post-grace term.
        self.user_not_terminated = create_test_user(
            [
                {
                    "term_date": (datetime.now(tz=settings.TZ).date() + timedelta(weeks=4)).strftime("%Y-%m-%d"),
                }
            ]
        )
        self.user_not_terminated.save()
        self.user_terminated = create_test_user(
            [
                {
                    "term_date": datetime.now(tz=settings.TZ).date().strftime("%Y-%m-%d"),
                }
            ]
        )
        self.user_terminated.save()
        self.user_terminated_after_grace = create_test_user(
            [
                {
                    "term_date": (datetime.now(tz=settings.TZ).date() + timedelta(weeks=-4)).strftime("%Y-%m-%d"),
                }
            ]
        )
        self.user_terminated_after_grace.save()

    @patch("organisation.management.commands.department_users_terminated_users_handling.remove_licenses")
    def test_remove_licenses_flag(self, mock_remove):
        cmd = Command()
        # No remove license flag test
        cmd.handle(remove_licenses=False, terminated_account_days=14)
        mock_remove.assert_not_called()

        # License removal flag used test
        # Also tests standard, within grace, and outside of grace terminations
        cmd.handle(remove_licenses=True, terminated_account_days=14)
        mock_remove.assert_called_once()

    @patch("organisation.management.commands.department_users_terminated_users_handling.remove_licenses")
    def test_terminated_account_days_flag(self, mock_remove):
        cmd = Command()
        # Grace period over all termination records
        # Also tests zero terminatable users
        cmd.handle(remove_licenses=True, terminated_account_days=30)
        mock_remove.assert_not_called()

        # Grace Period under 2 termination records
        # ALso tests multiple terminatable users
        cmd.handle(remove_licenses=True, terminated_account_days=0)
        self.assertEqual(mock_remove.call_count, 2)

    @patch("organisation.management.commands.department_users_terminated_users_handling.remove_licenses")
    def test_invalid_term_data(self, mock_remove):
        cmd = Command()
        # Handles invalid and can still post-grace terminations
        self.user_terminated.term_date_data = [
            {
                "term_date": "",
            }
        ]
        self.user_terminated.save()
        self.user_not_terminated.term_date_data = [
            {
                "term_date": None,
            }
        ]
        self.user_not_terminated.save()
        cmd.handle(remove_licenses=True, terminated_account_days=14)
        mock_remove.assert_called_once()

    @patch("organisation.management.commands.department_users_terminated_users_handling.remove_licenses")
    def test_no_term_data(self, mock_remove):
        # Tests zero term data available
        cmd = Command()
        self.user_terminated.term_date_data = []
        self.user_terminated.save()
        self.user_not_terminated.term_date_data = []
        self.user_not_terminated.save()
        self.user_terminated_after_grace.term_date_data = []
        self.user_terminated_after_grace.save()
        cmd.handle(remove_licenses=True, terminated_account_days=0)
        # ignorese invalid and still processes the valid
        mock_remove.assert_not_called()


# Creates a DepartmentUser object for testing
def create_test_user(term_date_data):
    return mixer.blend(
        DepartmentUser,
        active=True,
        email=mixer.RANDOM,
        given_name=mixer.RANDOM,
        surname=mixer.RANDOM,
        employee_id=mixer.RANDOM,
        dir_sync_enabled=True,
        azure_guid=mixer.RANDOM,
        term_date_data=term_date_data,
    )


class GenerateDummyDataTestCase(TestCase):
    """Test the organisation_generate_dummy_data management command."""

    @override_settings(DEBUG=False)
    def test_command_refuses_when_not_debug(self):
        """Command raises CommandError and creates nothing when DEBUG=False."""
        with self.assertRaises(CommandError):
            call_command("organisation_generate_dummy_data")
        self.assertEqual(Location.objects.count(), 0)
        self.assertEqual(CostCentre.objects.count(), 0)
        self.assertEqual(DepartmentUser.objects.count(), 0)

    @override_settings(DEBUG=True)
    def test_generates_default_counts(self):
        """DEBUG=True with default options creates 5 locations, 5 cost centres, 20 users with valid data."""
        out = StringIO()
        call_command("organisation_generate_dummy_data", stdout=out)
        self.assertEqual(Location.objects.count(), 5)
        self.assertEqual(CostCentre.objects.count(), 5)
        self.assertEqual(DepartmentUser.objects.count(), 20)
        self.assertIn("Created 5 locations, 5 cost centres and 20 department users", out.getvalue())
        for u in DepartmentUser.objects.all():
            self.assertIsNotNone(u.cost_centre)
            self.assertIsNotNone(u.location)
            self.assertIsNotNone(u.account_type)
            self.assertTrue(u.ascender_data)
            self.assertIn(u.ascender_data["emp_status"], EMP_STATUS)
            self.assertIn(u.ascender_data["clevel2_desc"], DIVISION_NAMES)
            self.assertTrue(u.get_division())
        self.assertEqual(DepartmentUser.objects.values("email").distinct().count(), 20)
        self.assertEqual(DepartmentUser.objects.filter(manager__isnull=True).count(), 1)
        self.assertTrue(CostCentre.objects.filter(manager__isnull=False).exists())
        for loc in Location.objects.all():
            self.assertIsNotNone(loc.point)

    @override_settings(DEBUG=True)
    def test_generates_custom_counts(self):
        """DEBUG=True with custom --locations/--cost-centres/--department-users creates that many records."""
        call_command("organisation_generate_dummy_data", locations=2, cost_centres=3, department_users=7, stdout=StringIO())
        self.assertEqual(Location.objects.count(), 2)
        self.assertEqual(CostCentre.objects.count(), 3)
        self.assertEqual(DepartmentUser.objects.count(), 7)

    @override_settings(DEBUG=True)
    def test_rejects_negative_counts(self):
        """Command raises CommandError when given a negative count."""
        with self.assertRaises(CommandError):
            call_command("organisation_generate_dummy_data", department_users=-1)

    def test_no_module_level_mixer_import(self):
        """The command module must not have a module-level mixer import."""
        import organisation.management.commands.organisation_generate_dummy_data as cmd

        self.assertFalse(hasattr(cmd, "mixer"))
