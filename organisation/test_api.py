from django.urls import reverse
from mixer.backend.django import mixer

from itassets.test_api import ApiTestCase
from organisation.models import Location


class DepartmentUserAPIResourceTestCase(ApiTestCase):
    def test_list(self):
        """Test the DepartmentUserAPIResource list responses"""
        url = reverse("department_user_api_resource")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Response should not contain inactive or shared accounts.
        self.assertContains(response, self.user1.email)
        self.assertContains(response, self.user2.email)
        self.assertNotContains(response, self.inactive_user.email)

    def test_list_filtering(self):
        """Test the DepartmentUserAPIResource filtered responses"""
        url = reverse("department_user_api_resource", kwargs={"pk": self.user1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user1.email)
        self.assertNotContains(response, self.user2.email)
        url = "{}?q={}".format(reverse("department_user_api_resource"), self.user2.email)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.user1.email)
        self.assertContains(response, self.user2.email)

    def test_list_tailored(self):
        """Test the LocationAPIResource tailored list responses"""
        # Test the "selectlist" response.
        url = "{}?selectlist=".format(reverse("department_user_api_resource"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class LocationAPIResourceTestCase(ApiTestCase):
    def test_list(self):
        """Test the LocationAPIResource list response"""
        loc_inactive = mixer.blend(Location, manager=None, active=False)
        url = reverse("location_api_resource")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.loc1.name)
        # Response should not contain the inactive Location.
        self.assertNotContains(response, loc_inactive.name)

    def test_list_filtering(self):
        """Test the LocationAPIResource filtered response"""
        url = reverse("location_api_resource", kwargs={"pk": self.loc1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.loc1.name)
        self.assertNotContains(response, self.loc2.name)
        url = "{}?q={}".format(reverse("location_api_resource"), self.loc2.name)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.loc1.name)
        self.assertContains(response, self.loc2.name)

    def test_list_tailored(self):
        """Test the LocationAPIResource tailored list responses"""
        # Test the "selectlist" response.
        url = "{}?selectlist=".format(reverse("location_api_resource"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class LicenseAPIResourceTestCase(ApiTestCase):
    def setUp(self):
        super(LicenseAPIResourceTestCase, self).setUp()
        self.user1.assigned_licences = ["MICROSOFT 365 E5"]
        self.user1.save()
        self.user2.assigned_licences = ["OFFICE 365 E1"]
        self.user2.save()

    def test_list(self):
        """Test the LicenseAPIResource list response"""
        url = reverse("license_api_resource")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user1.email)
        self.assertContains(response, self.user2.email)

    def test_filter(self):
        """Test the LicenseAPIResource filtered response"""
        url = reverse("license_api_resource", kwargs={"pk": self.user1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user1.email)
        self.assertNotContains(response, self.user2.email)
        url = "{}?q={}".format(reverse("license_api_resource"), self.user2.email)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.user1.email)
        self.assertContains(response, self.user2.email)
