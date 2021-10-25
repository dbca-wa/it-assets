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
        self.user.assigned_licences = ['OFFICE 365 E5']
        self.user.save()
        self.assertEqual(self.user.get_licence(), 'On-premise')
        self.user.assigned_licences = ['OFFICE 365 E1', 'bar']
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

    def test_generate_ad_actions_no_guid(self):
        self.assertEqual(self.user.generate_ad_actions(), [])

    def test_generate_ad_actions_onprem_displayname(self):
        self.user.ad_guid = uuid1
        self.user.ad_data = {
            'DisplayName': random_string(),
        }
        self.user.save()
        actions = self.user.generate_ad_actions()
        self.assertTrue(actions)
        self.assertEqual(actions[0].ad_field, 'DisplayName')

    def test_generate_ad_actions_azure_displayname(self):
        self.user.dir_sync_enabled = False
        self.user.azure_guid = uuid1
        self.user.azure_ad_data = {
            'displayName': random_string(),
        }
        self.user.save()
        actions = self.user.generate_ad_actions()
        self.assertTrue(actions)
        self.assertEqual(actions[0].ad_field, 'DisplayName')

    # GivenName, Surname, Title and EmployeeId are basically the same as DisplayName.

    def test_generate_ad_actions_onprem_telephone(self):
        self.user.ad_guid = uuid1
        self.user.telephone = random.randint(1, 9999)
        self.user.ad_data = {
            'telephoneNumber': None,
        }
        self.user.save()
        actions = self.user.generate_ad_actions()
        self.assertTrue(actions)
        # Invert values.
        self.user.telephone = None
        self.user.ad_data = {
            'telephoneNumber': random.randint(1, 9999),
        }
        self.user.save()
        actions = self.user.generate_ad_actions()
        self.assertTrue(actions)

    def test_generate_ad_actions_onprem_telephone_falsy(self):
        # Compare falsy but different values.
        self.user.ad_guid = uuid1
        self.user.telephone = None
        self.user.ad_data = {
            'telephoneNumber': '',
        }
        self.user.save()
        actions = self.user.generate_ad_actions()
        self.assertFalse(actions)

    # Mobile is basically the same as telephoneNumber, and Azure AD is the same as onprem.

    def test_generate_azure_ad_actions_cost_centre(self):
        self.user.dir_sync_enabled = False
        self.user.azure_guid = uuid1
        # Case 1: CC is set locally, no CC is set in Azure AD.
        self.user.cost_centre = self.cc
        self.user.azure_ad_data = {
            'companyName': None,
        }
        self.user.save()
        actions = self.user.generate_ad_actions()
        self.assertTrue(actions)
        # Case 2: different CC is set in each.
        self.user.azure_ad_data = {
            'companyName': random_string(),
        }
        self.user.save()
        actions = self.user.generate_ad_actions()
        self.assertTrue(actions)
        # Case 3: no CC is set locally, Azure AD has CC set.
        self.user.cost_centre = None
        self.user.save()
        actions = self.user.generate_ad_actions()
        self.assertTrue(actions)

    def test_generate_ad_actions_manager(self):
        self.user.ad_guid = uuid1
        # Case 1: manager is set locally, no manager is set in AD.
        self.user.manager = self.manager
        self.user.ad_data = {
            'Manager': None,
        }
        self.user.save()
        actions = self.user.generate_ad_actions()
        self.assertTrue(actions)
        # Case 2: different manager set in each.
        self.user.ad_data = {
            'Manager': random_string(),
        }
        self.user.save()
        actions = self.user.generate_ad_actions()
        self.assertTrue(actions)
        # Case 3: no manager set locally, AD has manager set.
        self.user.manager = None
        self.user.ad_data = {
            'Manager': self.manager.ad_data['DistinguishedName'],
        }
        self.user.save()
        actions = self.user.generate_ad_actions()
        self.assertTrue(actions)

    def test_generate_azure_ad_actions_manager(self):
        self.user.dir_sync_enabled = False
        self.user.azure_guid = uuid1
        # Case 1: manager is set locally, no manager is set in AD.
        self.user.manager = self.manager
        self.user.azure_ad_data = {
            'manager': None,
        }
        self.user.save()
        actions = self.user.generate_ad_actions()
        self.assertTrue(actions)
        # Case 2: different manager set in each.
        self.user.azure_ad_data = {
            'manager': {'id': random_string()},
        }
        self.user.save()
        actions = self.user.generate_ad_actions()
        self.assertTrue(actions)
        # Case 3: no manager set locally, AD has manager set.
        self.user.manager = None
        self.user.azure_ad_data = {
            'manager': {'id': self.manager.azure_guid},
        }
        self.user.save()
        actions = self.user.generate_ad_actions()
        self.assertTrue(actions)
