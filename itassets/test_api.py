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
        # Generate some locations.
        self.loc1 = mixer.blend(Location, manager=None)
        self.loc2 = mixer.blend(Location, manager=None)

        # Generate a basic org structure.
        self.dept = OrgUnit.objects.create(name='Department 1', unit_type=0, acronym='DEPT', active=True)
        self.div1 = OrgUnit.objects.create(
            name='Divison 1', unit_type=1, division_unit=self.dept, location=self.loc1, acronym='DIV1', active=True)
        self.branch1 = OrgUnit.objects.create(
            name='Branch 1', unit_type=2, division_unit=self.div1, location=self.loc1, acronym='BRANCH1', active=True)
        self.cc1 = CostCentre.objects.create(code='001', division_name=self.div1.name)
        self.div2 = OrgUnit.objects.create(
            name='Divison 2', unit_type=1, division_unit=self.dept, location=self.loc2, acronym='DIV2', active=True)
        self.branch2 = OrgUnit.objects.create(
            name='Branch 2', unit_type=2, division_unit=self.div2, location=self.loc2, acronym='BRANCH2', active=True)
        self.cc2 = CostCentre.objects.create(code='002', division_name=self.div2.name)

        # Generate some other DepartmentUser objects.
        self.user1 = mixer.blend(
            DepartmentUser, active=True,
            email=random_dbca_email, org_unit=None, ad_guid=uuid1, in_sync=False,
            account_type=2,  # Permanent
            cost_centre=self.cc1,
        )
        self.user2 = mixer.blend(
            DepartmentUser, active=True,
            email=random_dbca_email, org_unit=None, ad_guid=uuid1, in_sync=False,
            account_type=3,  # Agency contract
            cost_centre=self.cc1,
        )
        self.inactive_user = mixer.blend(
            DepartmentUser, active=False,
            email=random_dbca_email, org_unit=None, ad_guid=uuid1, in_sync=False,
            account_type=2,
            cost_centre=self.cc1,
        )
        self.shared_acct = mixer.blend(
            DepartmentUser, active=True,
            email=random_dbca_email, org_unit=None, ad_guid=uuid1, in_sync=False,
            account_type=5,  # Shared account
            cost_centre=self.cc1,
        )
        self.contractor = mixer.blend(
            DepartmentUser, active=True,
            email=random_dbca_email, org_unit=None, ad_guid=uuid1, in_sync=False,
            contractor=True,
            account_type=0,  # Fixed term contract
            cost_centre=self.cc1,
        )

        # Generate a test user for endpoint responses.
        self.testuser = User.objects.create_user(
            username='testuser', email='user@dbca.wa.gov.au.com', password='pass')
        # Create a DepartmentUser object for testuser.
        mixer.blend(
            DepartmentUser, active=True, email=self.testuser.email,
            org_unit=None, cost_centre=None, ad_guid=uuid1)
        # Log in testuser by default.
        self.client.login(username='testuser', password='pass')

        # Generate some IT Systems.
        self.it_prod = mixer.blend(ITSystem, status=0, owner=self.user1)  # Production
        self.it_dev = mixer.blend(ITSystem, status=1, owner=self.user2)  # Development
        self.it_leg = mixer.blend(ITSystem, status=2, owner=self.user2)  # Production legacy
        self.it_dec = mixer.blend(ITSystem, status=3, owner=self.user2)  # Decommissioned
