from django.urls import reverse
from itassets.test_api import ApiTestCase

from assets.tests.test_model import RandomAssetGenerator as Gen

import json


class AssetsAPITestCase(ApiTestCase):
    def setUp(self):
        self.asset1, self.asset2, self.asset3 = Gen().generate(3)
        self.asset1.save()
        self.asset2.save()
        self.asset3.save()

    def test_populated(self):
        """
        Tests standard get call to assets endpoint, and data retrieval.
        """
        url = reverse("asset_api_resource")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.asset1.name)
        self.assertContains(resp, self.asset2.name)
        self.assertContains(resp, self.asset3.name)

    def test_empty(self):
        """
        Tests that an empty asset database will return empty
        """
        asset1_name = self.asset1.name
        self.asset1.delete()
        self.asset2.delete()
        self.asset3.delete()
        url = reverse("asset_api_resource")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content), [])

        # Tests filtering on empty asset database
        url = reverse("asset_api_resource", query={"name": asset1_name})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content), [])

    def test_show_tenable_data(self):
        """
        Tests that tenable data is hidden and show appropriately depending on the flag.
        """
        self.asset1.tenable_data = {"test_tenable_data_key": "test_tenable_data_result"}
        self.asset1.save()

        # Confirms that the data is visible when flagged
        url = "{}?tenable_data_only".format(reverse("asset_api_resource"))
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "test_tenable_data_key")
        self.assertContains(resp, "test_tenable_data_result")
        # Validates that it's exclusively showing the tenable data
        self.assertNotContains(resp, self.asset1.name)
        self.assertNotContains(resp, self.asset2.name)
        self.assertNotContains(resp, self.asset3.name)

        # Confirms that the data is hidden when not flagged
        url = reverse("asset_api_resource")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "test_tenable_data_key")
        self.assertNotContains(resp, "test_tenable_data_result")

    def test_filter_pk(self):
        """
        Tests filtering by PK
        """

        # Test pk found
        url = reverse("asset_api_resource", kwargs={"pk": self.asset1.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.asset1.name)
        self.assertNotContains(resp, self.asset2.name)
        self.assertNotContains(resp, self.asset3.name)

        # Test pk not found
        url = reverse("asset_api_resource", kwargs={"pk": self.asset1.pk + 4})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content), [])

    def test_filter_name(self):
        """
        Tests filtering by name
        """
        # Test name found
        url = reverse("asset_api_resource", query={"name": self.asset1.name})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.asset1.name)

        # Test name not found
        url = reverse("asset_api_resource", query={"name": self.asset1.name + "FAKENAME"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content), [])

    def test_filter_tags(self):
        """
        Tests filtering by tags
        """

        self.asset1.add_tag(tag="tag_val", category="tag_cat_1")
        self.asset1.save()
        self.asset2.add_tag(tag="tag_val", category="tag_cat_2")
        self.asset2.save()
        self.asset3.add_tag(tag="tag_val_diff", category="tag_cat_1")
        self.asset3.save()

        # Test tag cat found
        url = reverse("asset_api_resource", query={"tag_cat": "tag_cat_1"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.asset1.name)
        self.assertContains(resp, self.asset3.name)
        self.assertNotContains(resp, self.asset2.name)

        # Test tag cat not found
        url = reverse("asset_api_resource", query={"tag_cat": "tag_cat"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, self.asset1.name)
        self.assertNotContains(resp, self.asset2.name)
        self.assertNotContains(resp, self.asset3.name)

        # Test tag value found
        url = reverse("asset_api_resource", query={"tag": "tag_val"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.asset1.name)
        self.assertContains(resp, self.asset2.name)
        self.assertNotContains(resp, self.asset3.name)

        # Test tag value not found
        url = reverse("asset_api_resource", query={"tag": "tag"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, self.asset1.name)
        self.assertNotContains(resp, self.asset2.name)
        self.assertNotContains(resp, self.asset3.name)

        # Test tag value in tag cat found
        url = reverse("asset_api_resource", query={"tag": "tag_val", "tag_cat": "tag_cat_1"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.asset1.name)
        self.assertNotContains(resp, self.asset2.name)
        self.assertNotContains(resp, self.asset3.name)

        # Test tag val found, but not cat
        url = reverse("asset_api_resource", query={"tag": "tag_val", "tag_cat": "tag"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, self.asset1.name)
        self.assertNotContains(resp, self.asset2.name)
        self.assertNotContains(resp, self.asset3.name)

        # Test tag cat found, but not tag val
        url = reverse("asset_api_resource", query={"tag": "tag", "tag_cat": "tag_cat_1"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, self.asset1.name)
        self.assertNotContains(resp, self.asset2.name)
        self.assertNotContains(resp, self.asset3.name)

        # Test assert none found
        url = reverse("asset_api_resource", query={"tag": "tag", "tag_cat": "tag"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, self.asset1.name)
        self.assertNotContains(resp, self.asset2.name)
        self.assertNotContains(resp, self.asset3.name)
