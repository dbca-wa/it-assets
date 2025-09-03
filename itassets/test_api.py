from uuid import uuid1

from django.contrib.auth.models import User
from django.test import Client, TestCase
from mixer.backend.django import mixer

from organisation.models import CostCentre, DepartmentUser, Location
from registers.models import ITSystem


def random_dbca_email():
    """Return a random email address ending in dbca.wa.gov.au"""
    return f"{mixer.faker.first_name()}.{mixer.faker.last_name()}@dbca.wa.gov.au".lower()


class ApiTestCase(TestCase):
    client = Client()

    def setUp(self):
        # Generate some locations.
        self.loc1 = mixer.blend(Location, manager=None)
        self.loc2 = mixer.blend(Location, manager=None)

        # Generate a basic org structure.
        self.cc1 = CostCentre.objects.create(code="001", division_name="Division A")
        self.cc2 = CostCentre.objects.create(code="002", division_name="Division B")

        # Generate some other DepartmentUser objects.
        self.user_permanent = mixer.blend(
            DepartmentUser,
            active=True,
            email=random_dbca_email,
            ad_guid=uuid1,
            in_sync=False,
            account_type=2,  # Permanent
            cost_centre=self.cc1,
            assigned_licences=["MICROSOFT 365 E5"],
        )
        self.user_contract = mixer.blend(
            DepartmentUser,
            active=True,
            email=random_dbca_email,
            ad_guid=uuid1,
            in_sync=False,
            account_type=0,  # Contract
            cost_centre=self.cc1,
            assigned_licences=["MICROSOFT 365 F3"],
        )
        self.inactive_user = mixer.blend(
            DepartmentUser,
            active=False,
            email=random_dbca_email,
            ad_guid=uuid1,
            in_sync=False,
            account_type=2,  # Permanent
            cost_centre=self.cc1,
        )

        # Generate a test user for endpoint responses.
        self.testuser = User.objects.create_user(username="testuser", email="user@dbca.wa.gov.au.com", password="pass")
        # Create a DepartmentUser object for testuser.
        mixer.blend(DepartmentUser, active=True, email=self.testuser.email, cost_centre=None, ad_guid=uuid1)
        # Log in testuser by default.
        self.client.login(username="testuser", password="pass")

        # Generate some IT Systems.
        self.it_prod = mixer.blend(ITSystem, status=0, owner=self.user_permanent)  # Production
        self.it_dev = mixer.blend(ITSystem, status=1, owner=self.user_contract)  # Development
        self.it_leg = mixer.blend(ITSystem, status=2, owner=self.user_contract)  # Production legacy
        self.it_dec = mixer.blend(ITSystem, status=3, owner=self.user_contract)  # Decommissioned
