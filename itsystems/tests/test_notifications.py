from django.test import TestCase, override_settings
from itsystems.notifications import send_daily_audit_email, send_user_deletion_email


class NotificationsTestCase(TestCase):
    @override_settings(
        IT_SYSTEMS_REGISTER_EMAIL="invalid_email", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
    )  # prevents sending emails during tests, and keeps it in local memory
    def test_user_deletion_email(self):
        """
        Tests that the sending of deletion emails contains the correct values.
        """
        msg = send_user_deletion_email(
            related_systems={"example_system1": ["example_field1"], "example_system2": ["example_field2", "example_field3"]},
            user="example_user",
        )
        self.assertIn("example_system1", msg.body)
        self.assertIn("example_system2", msg.body)
        self.assertIn("example_field1", msg.body)
        self.assertIn("example_field2", msg.body)
        self.assertIn("example_field3", msg.body)
        self.assertIn("example_user", msg.body)
        self.assertIn("invalid_email", msg.to)
        self.assertIn("example_user", msg.subject)

        msg = send_user_deletion_email(related_systems={}, user="example_user")
        self.assertEqual(msg, None)

    @override_settings(IT_SYSTEMS_REGISTER_EMAIL="invalid_email", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_contact_notification_email(self):
        """
        Tests that the sending of the daily audit email contains the correct values for each item sent to it.
        """
        flagged_users = [
            {
                "system_name": "example_sys1",
                "field_name": "example_field1",
                "user_email": "example_email1",
                "user_status": "example_status1",
            },
            {
                "system_name": "example_sys2",
                "field_name": "example_field2",
                "user_email": "example_email2",
                "user_status": "example_status2",
            },
        ]

        msg = send_daily_audit_email(flagged_users)

        for user in flagged_users:
            self.assertIn(user["system_name"], msg.body)
            self.assertIn(user["field_name"], msg.body)
            self.assertIn(user["user_email"], msg.body)
            self.assertIn(user["user_status"], msg.body)
