"""Tests for the organisation_generate_dummy_data management command."""

import logging
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from organisation.management.commands.organisation_generate_dummy_data import DIVISION_NAMES, EMP_STATUS
from organisation.models import CostCentre, DepartmentUser, Location

# Disable non-critical logging output.
logging.disable(logging.CRITICAL)


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
