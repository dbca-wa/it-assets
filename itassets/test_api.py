from django.contrib.auth.models import User
from django.test import TestCase, Client
from mixer.backend.django import mixer

from django.urls import reverse

import random
import string
from uuid import uuid1

from organisation.models import DepartmentUser, Location, OrgUnit, CostCentre
from registers.models import ITSystem


def random_dbca_email():
    """Return a random email address ending in dbca.wa.gov.au
    """
    s = ''.join(random.choice(string.ascii_letters) for i in range(20))
    return '{}@dbca.wa.gov.au'.format(s)


class ApiTestCase(TestCase):
    client = Client()

    def setUp(self):
        # Generate some other DepartmentUser objects.
        mixer.cycle(8).blend(
            DepartmentUser, username=mixer.RANDOM, photo=None, active=True,
            email=random_dbca_email, org_unit=None,
            cost_centre=None, ad_guid=uuid1, in_sync=False)
        # Generate some locations.
        self.loc1 = mixer.blend(Location, manager=None)
        self.loc2 = mixer.blend(Location, manager=None)
        # Generate a basic org structure.
        self.dept = OrgUnit.objects.create(name='Department 1', unit_type=0, acronym='DEPT', active=True)
        self.div1 = OrgUnit.objects.create(
            name='Divison 1', unit_type=1, division_unit=self.dept, location=self.loc1, acronym='DIV1', active=True)
        self.branch1 = OrgUnit.objects.create(
            name='Branch 1', unit_type=2, division_unit=self.div1, location=self.loc1, acronym='BRANCH1', active=True)
        self.cc1 = CostCentre.objects.create(
            code='001', division_name=self.div1.name, org_position=self.div1)
        self.div2 = OrgUnit.objects.create(
            name='Divison 2', unit_type=1, division_unit=self.dept, location=self.loc2, acronym='DIV2', active=True)
        self.branch2 = OrgUnit.objects.create(
            name='Branch 2', unit_type=2, division_unit=self.div2, location=self.loc2, acronym='BRANCH2', active=True)
        self.cc2 = CostCentre.objects.create(
            code='002', division_name=self.div2.name, org_position=self.div2)
        # Give each of the org units some members.
        users = DepartmentUser.objects.all()
        self.user1 = users[0]
        self.user1.org_unit = self.div1
        self.user1.cost_centre = self.cc1
        self.user1.save()
        self.div1.manager = self.user1
        self.div1.save()
        self.user2 = users[1]
        self.user2.org_unit = self.div2
        self.user2.cost_centre = self.cc2
        self.user2.save()
        self.div2.manager = self.user2
        self.div2.save()
        self.user3 = users[2]
        self.user3.org_unit = self.branch1
        self.user3.cost_centre = self.cc1
        self.user3.save()
        self.user4 = users[3]
        self.user4.org_unit = self.branch2
        self.user4.cost_centre = self.cc2
        self.user4.save()
        # Mark a user as inactive and deleted in AD.
        self.del_user = users[2]
        self.del_user.active = False
        self.del_user.ad_deleted = True
        self.del_user.org_unit = self.div2
        self.del_user.cost_centre = self.cc2
        self.del_user.save()
        # Make a contractor.
        self.contract_user = users[3]
        self.contract_user.contractor = True
        self.contract_user.org_unit = self.div2
        self.contract_user.cost_centre = self.cc2
        self.contract_user.save()
        # Make a shared account.
        self.shared = users[4]
        self.shared.account_type = 5  # Shared account type.
        self.shared.org_unit = self.div1
        self.shared.cost_centre = self.cc1
        self.shared.save()
        # Make a user that doesn't manage a division.
        self.user3 = users[5]
        self.user3.org_unit = self.div1
        self.user3.cost_centre = self.cc1
        self.user3.save()
        # Generate a test user for endpoint responses.
        self.testuser = User.objects.create_user(
            username='testuser', email='user@dbca.wa.gov.au.com', password='pass')
        # Create a DepartmentUser object for testuser.
        mixer.blend(
            DepartmentUser, username=mixer.RANDOM, photo=None, active=True, email=self.testuser.email,
            org_unit=None, cost_centre=None, ad_guid=uuid1)
        # Log in testuser by default.
        self.client.login(username='testuser', password='pass')
        # Generate some IT Systems.
        self.it1 = mixer.blend(ITSystem, status=0, owner=self.user1)
        self.it2 = mixer.blend(ITSystem, status=1, owner=self.user2)
        self.it_leg = mixer.blend(ITSystem, status=2, owner=self.user2)
        self.it_dec = mixer.blend(ITSystem, status=3, owner=self.user2)


class HealthCheckViewTestCase(TestCase):

    def test_get_context(self):
        url = reverse('health_check')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
