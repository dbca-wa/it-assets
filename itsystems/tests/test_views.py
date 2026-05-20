from django.urls import reverse

from itassets.test_api import ApiTestCase
from .test_model import create_random_record
from itsystems.models import Status


class ViewsTestCase(ApiTestCase):
    def test_it_systems_register_empty(self):
        """
        Test the it systems register view.
        Ensures that an empty database is displayed as such.
        """
        url = reverse("it_systems_register")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No results found")

    def test_it_systems_register_populated(self):
        """
        Test the it systems register view.
        Ensures that a populated database displays it's records
        """
        record1 = create_random_record()
        record2 = create_random_record()

        record1.save()
        record2.save()

        url = reverse("it_systems_register")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, record1.system_id)
        self.assertContains(resp, record2.system_id)
        self.assertNotContains(resp, "No results found")

    def test_it_systems_register_filtering(self):
        """
        Test the it systems register view.
        Ensures that a populated database can be accurately filtered.
        """
        record1 = create_random_record()
        record2 = create_random_record()

        record1.save()
        record2.save()

        # Tests Search
        url = reverse("it_systems_register") + "?q=" + str(record1.system_id)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, record1.system_id)
        self.assertNotContains(resp, record2.system_id)

        # Tests fk choice field filtering
        url = reverse("it_systems_register") + "?division=" + str(record2.division.id)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, record1.system_id)
        self.assertContains(resp, record2.system_id)

        # Tests boolean choice field filtering
        record1.vital_records = True
        record2.vital_records = False
        record1.save()
        record2.save()
        url = reverse("it_systems_register") + "?vital_records=" + str(record1.vital_records)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, record1.system_id)
        self.assertNotContains(resp, record2.system_id)

        # Tests filtering by contacts
        url = reverse("it_systems_register") + "?system_owner=" + str(record1.system_owner.id)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, record1.system_id)
        self.assertNotContains(resp, record2.system_id)

        # Tests failure to find from mismatch
        url = reverse("it_systems_register") + "?q=" + str(record2.name) + "&vital_records=" + str(record1.vital_records)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No results found")
        self.assertNotContains(resp, record1.system_id)
        self.assertNotContains(resp, record2.system_id)

        # Tests draft filtering
        draft_status = Status(name="Draft")
        draft_status.save()
        record1.status = draft_status
        record1.save()
        url = reverse("it_systems_register") + "?show_drafts=True"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, record1.system_id)
        self.assertContains(resp, record2.system_id)

        url = reverse("it_systems_register")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, record1.system_id)
        self.assertContains(resp, record2.system_id)