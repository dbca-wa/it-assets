from django.test import TestCase
from mixer.backend.django import mixer
import random
import string
from uuid import uuid1

from itassets.test_api import random_dbca_email
from organisation.models import DepartmentUser, CostCentre


def random_string(len=10):
    """Return a random string of arbitary length.
    """
    return ''.join(random.choice(string.ascii_letters) for i in range(len))


class DepartmentUserTestCase(TestCase):

    def setUp(self):
        self.user = mixer.blend(
            DepartmentUser,
            active=True,
            email=random_dbca_email,
            given_name=mixer.RANDOM,
            surname=mixer.RANDOM,
            employee_id=mixer.RANDOM,
            shared_account=False,
            dir_sync_enabled=True,
        )
        self.manager = mixer.blend(
            DepartmentUser,
            active=True,
            email=random_dbca_email,
            given_name=mixer.RANDOM,
            surname=mixer.RANDOM,
            employee_id=mixer.RANDOM,
            shared_account=False,
            dir_sync_enabled=True,
            ad_data={'DistinguishedName': random_string()},
            azure_guid=uuid1,
        )
        self.cc = mixer.blend(
            CostCentre,
            active=True,
            division_name=mixer.RANDOM,
        )

    def test_save(self):
        self.assertTrue(self.user.employee_id)
        self.assertFalse(self.user.shared_account)
        self.user.employee_id = 'N/A'
        self.user.account_type = 5
        self.user.save()
        self.assertFalse(self.user.employee_id)
        self.assertTrue(self.user.shared_account)

    def test_get_licence(self):
        self.assertFalse(self.user.get_licence())
        self.user.assigned_licences = ['MICROSOFT 365 E5', 'foo']
        self.user.save()
        self.assertEqual(self.user.get_licence(), 'On-premise')
        self.user.assigned_licences = ['MICROSOFT 365 F3', 'bar']
        self.user.save()
        self.assertEqual(self.user.get_licence(), 'Cloud')
        self.user.assigned_licences = ['foo', 'bar']
        self.user.save()
        self.assertFalse(self.user.get_licence())

    def test_get_full_name(self):
        self.assertEqual(self.user.get_full_name(), '{} {}'.format(self.user.given_name, self.user.surname))
        self.user.given_name = None
        self.user.save()
        self.assertEqual(self.user.get_full_name(), self.user.surname)
