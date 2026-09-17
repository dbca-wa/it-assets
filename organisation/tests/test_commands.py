from django.test import TestCase
from mixer.backend.django import mixer

from unittest.mock import patch
from datetime import date, timedelta

from organisation.management.commands.department_users_terminated_users_handling import Command
from organisation.models import DepartmentUser


class TerminatedUsersTestCase(TestCase):
    def setUp(self) -> None:
        # 1 user not-term, 1 user term, 1 user post-grace term.
        self.user_not_terminated = create_test_user(
            [
                {
                    "term_date": (date.today() + timedelta(weeks=4)).strftime("%Y-%m-%d"),
                }
            ]
        )
        self.user_not_terminated.save()
        self.user_terminated = create_test_user(
            [
                {
                    "term_date": date.today().strftime("%Y-%m-%d"),
                }
            ]
        )
        self.user_terminated.save()
        self.user_terminated_after_grace = create_test_user(
            [
                {
                    "term_date": (date.today() + timedelta(weeks=-4)).strftime("%Y-%m-%d"),
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
