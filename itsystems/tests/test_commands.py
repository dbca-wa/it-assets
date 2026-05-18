from django.test import TestCase, override_settings
from itsystems.management.commands.it_systems_register_contact_notification import Command
from .test_model import create_random_record
from ..models import ITSystemRecord

class CommandsTestCase(TestCase):
    
    @override_settings(IT_SYSTEMS_REGISTER_EMAIL="invalid_email", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend") # prevents sending emails during tests, and keeps it in local memory
    def test_contact_notification(self):
        """
        Tests that the audit captures and displays all users with invalid statuses and missing users from mandatory fields, and ignores users who are not a concern.
        """
        # Create records & users - all users default to status: unknown, and as such by default will be picked up by the audit.
        record1 = create_random_record()
        record2 = create_random_record()
        record3 = create_random_record()
        record1.save()
        record2.save()
        record3.save()
        records = ITSystemRecord.objects.all()

        # Record 1: Makes all valid
        record1.business_service_owner.account_type = 2
        record1.business_service_owner.save()
        record1.system_owner.account_type  = 2
        record1.system_owner.save()
        record1.technology_custodian.account_type  = 2
        record1.technology_custodian.save()
        record1.information_custodian.account_type  = 2
        record1.information_custodian.save()

        # Record 2: Removes a mandatory contact and a non-mandatory contact, and makes the rest valid
        record2.business_service_owner.delete()
        record2.system_owner.account_type  = 2
        record2.system_owner.save()
        record2.technology_custodian.account_type  = 2
        record2.technology_custodian.save()
        record2.information_custodian.delete()

        # Record 3: Keeps all invalid

        # Runs audit function
        cmd = Command()
        msg = cmd.handle(send_email=True, return_msg=True)

        # ensures that all contacts in record 3 are reported
        self.assertIn(record3.business_service_owner.email, msg.body)
        self.assertIn(record3.system_owner.email, msg.body)
        self.assertIn(record3.technology_custodian.email, msg.body)
        self.assertIn(record3.information_custodian.email, msg.body)

        # ensures that record 2 is only mentioned once for the empty value
        self.assertEqual(msg.body.count(str(record2)),1)
        self.assertEqual(msg.body.count("EMPTY"), 2)

        # ensures that record 1 isn't present at all
        self.assertNotIn(str(record1), msg.body)