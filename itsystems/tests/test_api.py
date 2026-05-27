from django.urls import reverse

import json

from itassets.test_api import ApiTestCase
from .test_model import create_random_record
from itsystems.models import ITSystemRecord
from reversion.models import Version


class ITSystemRecordAPIResourceTestCase(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.record1 = create_random_record()
        self.record2 = create_random_record()
        self.record3 = create_random_record()
        self.record1.save()
        self.record2.save()
        self.record3.save()
        self.records = ITSystemRecord.objects.all()

    def test_list(self):
        """Test the ITSystemRecordAPIResource list responses"""
        url = reverse("it_system_api_resource")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        # Response should contain each of the records, and should match the size of the database
        for record in self.records:
            self.assert_response_contains_record(response, record)
        content = json.loads(response.content)
        self.assertEqual(len(content), 3)

    def test_search(self):
        """Test the ITSystemRecordAPIResource search for record functionality"""

        # Searches for a record, ensuring it and only it is present
        url = reverse("it_system_api_resource", kwargs={"system_id": self.record1.system_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assert_response_contains_record(response, self.record1)
        self.assert_response_does_not_contain_record(response, self.record2)
        self.assert_response_does_not_contain_record(response, self.record3)

        # Searches for a record that doesn't exist, ensuring that nothing is returned
        url = reverse("it_system_api_resource", kwargs={"system_id": self.record1.system_id + "EXTRA_STRING"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assert_response_does_not_contain_record(response, self.record1)
        self.assert_response_does_not_contain_record(response, self.record2)
        self.assert_response_does_not_contain_record(response, self.record3)

    def test_record_edit(self):
        """Test the ITSystemRecordAPIResource edit record functionality"""

        # Tests changing the name of an existing record
        old_name = self.record1.name
        new_name = old_name[:-5] + "added_string"
        url = reverse("it_system_api_resource", kwargs={"system_id": self.record1.system_id})
        response = self.client.post(path=url, data=json.dumps({"name": new_name}), secure=False, content_type="application/json")
        self.record1 = ITSystemRecord.objects.get(pk=self.record1.pk)
        self.assertContains(response, status_code=200, text=new_name)
        self.assertNotContains(response, old_name)
        self.assertEqual(self.record1.name, new_name)
        # confirms modified by behaviour
        self.assertEqual(self.record1.modified_by, self.testuser.email)
        self.assertNotEqual(self.record1.created_by, self.testuser.email)
        # confirms that a new version was created
        versions = Version.objects.get_for_object(self.record1)
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].field_dict["name"], new_name)

        # Tests changing an FK field of an existing record
        old_division = self.record1.division.name
        old_division_id = self.record1.division.id
        new_division = self.record2.division.name
        new_division_id = self.record2.division.id
        url = reverse("it_system_api_resource", kwargs={"system_id": self.record1.system_id})
        response = self.client.post(path=url, data=json.dumps({"division": new_division}), secure=False, content_type="application/json")
        self.record1 = ITSystemRecord.objects.get(pk=self.record1.pk)
        self.assertContains(response, status_code=200, text=new_division)
        self.assertNotContains(response, old_division)
        self.assertEqual(self.record1.division.name, new_division)
        # confirms that a new version was created
        versions = Version.objects.get_for_object(self.record1)
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0].field_dict["division_id"], new_division_id)
        self.assertEqual(versions[1].field_dict["division_id"], old_division_id)

        # Tests changing the name of a record that doesn't exist
        old_name = self.record1.name
        new_name = old_name + "ADDED_STRING"
        url = reverse("it_system_api_resource", kwargs={"system_id": self.record1.system_id + "ADDED_STRING"})
        response = self.client.post(path=url, data=json.dumps({"name": new_name}), secure=False, content_type="application/json")
        self.record1 = ITSystemRecord.objects.get(pk=self.record1.pk)
        self.assertContains(response=response, status_code=400, text="Can't find system ")
        self.assertEqual(self.record1.name, old_name)

        # Tests changing an FK field of an existing record to one that doesn't exist
        old_division = self.record1.division.name
        fake_division = self.record1.division.name + "ADDED_STRING"
        url = reverse("it_system_api_resource", kwargs={"system_id": self.record1.system_id})
        response = self.client.post(path=url, data=json.dumps({"division": fake_division}), secure=False, content_type="application/json")
        self.record1 = ITSystemRecord.objects.get(pk=self.record1.pk)
        self.assertContains(response, status_code=400, text="Invalid field value in choice field")
        self.assertEqual(self.record1.division.name, old_division)

        # Tests that attempting to change a field that doesn't exist doesn't change the record at all
        url = reverse("it_system_api_resource", kwargs={"system_id": self.record1.system_id})
        response = self.client.post(path=url, data=json.dumps({"fake_field": "fake_value"}), secure=False, content_type="application/json")
        self.record1 = ITSystemRecord.objects.get(pk=self.record1.pk)
        self.assertEqual(response.status_code, 200)
        self.assert_response_contains_record(response, self.record1)

        # Tests that sending identical data doesn't cause the new versions to be created
        original_num_versions = len(Version.objects.get_for_object(self.record1))
        url = reverse("it_system_api_resource", kwargs={"system_id": self.record1.system_id})
        response = self.client.post(
            path=url,
            data=json.dumps({"name": self.record1.name, "description": self.record1.description}),
            secure=False,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        versions = Version.objects.get_for_object(self.record1)
        self.assertEqual(len(versions), original_num_versions)

        # Tests that identical data doesn't get included in version history comments
        url = reverse("it_system_api_resource", kwargs={"system_id": self.record1.system_id})
        response = self.client.post(
            path=url,
            data=json.dumps(
                {
                    "description": (self.record1.description + "_ADDED_VALUE"),
                    "name": self.record1.name,
                    "business_service_owner": self.record1.business_service_owner.email,
                }
            ),
            secure=False,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        versions = Version.objects.get_for_object(self.record1)
        self.assertIn("Description", versions[0].revision.get_comment())
        self.assertNotIn("Name", versions[0].revision.get_comment())
        self.assertNotIn("Business Service Owner", versions[0].revision.get_comment())

        # Tests that empty strings are treated as Null, but mandatory fields throw exceptions
        empty_record = {
            "name": "",
            "status": "",
            "division": "",
            "description": "",
            "link": "",
            "business_service_owner": "",
            "system_owner": "",
            "technology_custodian": "",
            "information_custodian": "",
            "seasonality": "",
            "availability": "",
            "file_store_link": "",
            "vital_records": "",
            "disposal_authority": "",
            "retention_and_disposal": "",
            "ubcs": "",
            "sensitivity": "",
            "system_type": "",
        }
        url = reverse("it_system_api_resource", kwargs={"system_id": self.record1.system_id})
        response = self.client.post(
            path=url,
            data=json.dumps(empty_record),
            secure=False,
            content_type="application/json",
        )
        self.assertContains(response, status_code=400, text="Empty value in mandatory choice field")
        empty_record = {
            "name": "",
            "division": "",
            "description": "",
            "link": "",
            "business_service_owner": "",
            "system_owner": "",
            "technology_custodian": "",
            "information_custodian": "",
            "file_store_link": "",
            "vital_records": "",
            "disposal_authority": "",
            "retention_and_disposal": "",
            "ubcs": "",
            "sensitivity": "",
            "system_type": "",
        }
        url = reverse("it_system_api_resource", kwargs={"system_id": self.record1.system_id})
        response = self.client.post(
            path=url,
            data=json.dumps(empty_record),
            secure=False,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_contact_replace(self):
        """Test the ITSystemRecordAPIResource replace contact functionality"""

        target1 = self.records[0]
        target2 = self.records[1]
        non_target = self.records[2]

        target1.technology_custodian = target2.business_service_owner
        target1.information_custodian = target2.business_service_owner
        target1.save()

        old_contact = target2.business_service_owner.email
        new_contact = target1.business_service_owner.email

        url = reverse("it_system_api_resource")
        json_data = json.dumps({"new_contact": new_contact, "old_contact": old_contact})
        response = self.client.post(path=url, data=json_data, secure=False, content_type="application/json")

        # Ensures response is correct
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, target1.system_id)
        self.assertContains(response, target2.system_id)
        self.assertNotContains(response, non_target.system_id)
        self.assertContains(response, "business_service_owner")
        self.assertContains(response, "technology_custodian")
        self.assertContains(response, "information_custodian")
        self.assertNotContains(response, "system_owner")

        target1 = ITSystemRecord.objects.get(pk=target1.pk)
        target2 = ITSystemRecord.objects.get(pk=target2.pk)
        non_target = ITSystemRecord.objects.get(pk=non_target.pk)

        # Ensures that relevant information has been properly updated
        self.assertEqual(target1.technology_custodian.email, new_contact)
        self.assertEqual(target1.information_custodian.email, new_contact)
        self.assertEqual(target2.business_service_owner.email, new_contact)

        # confirms modified by behaviour
        self.assertEqual(target1.modified_by, self.testuser.email)
        self.assertNotEqual(target1.created_by, self.testuser.email)

        # confirms that a new version was created
        versions = Version.objects.get_for_object(target1)
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].field_dict["technology_custodian_id"], target2.business_service_owner.id)

        # Tests replacing a user that doesn't exist
        existing_user = target2.business_service_owner.email
        fake_user = existing_user[:-5] + "__ADDED_STRING"

        url = reverse("it_system_api_resource")
        json_data = json.dumps({"new_contact": fake_user, "old_contact": existing_user})
        response = self.client.post(path=url, data=json_data, secure=False, content_type="application/json")

        self.assertContains(response=response, status_code=400, text="Invalid user email")

        # Tests replacing a user that exists but isn't used anywhere
        unused_user = self.user_permanent.email
        existing_contact = self.record1.business_service_owner.email

        url = reverse("it_system_api_resource")
        json_data = json.dumps({"new_contact": existing_contact, "old_contact": unused_user})
        response = self.client.post(path=url, data=json_data, secure=False, content_type="application/json")
        self.assertContains(response=response, status_code=200, text="[]")

    def assert_response_contains_record(self, response, record):
        """Tests that the inputted record exists in the response"""
        self.assertContains(response, record.system_id)
        self.assertContains(response, record.name)
        self.assertContains(response, record.status.name)
        self.assertContains(response, record.division.name)
        self.assertContains(response, record.business_service_owner.email)
        self.assertContains(response, record.system_owner.email)
        self.assertContains(response, record.technology_custodian.email)
        self.assertContains(response, record.information_custodian.email)
        self.assertContains(response, record.seasonality.name)
        self.assertContains(response, record.availability.name)
        self.assertContains(response, record.sensitivity.name)
        self.assertContains(response, record.system_type.name)
        self.assertContains(response, record.description.replace("\n", "\\n"))

    def assert_response_does_not_contain_record(self, response, record):
        """Tests that the inputted record does not exist in the record. Doesn't include non-unique FK values, as they can appear in other records"""
        self.assertNotContains(response, record.system_id)
        self.assertNotContains(response, record.name)
        self.assertNotContains(response, record.business_service_owner.email)
        self.assertNotContains(response, record.system_owner.email)
        self.assertNotContains(response, record.technology_custodian.email)
        self.assertNotContains(response, record.information_custodian.email)
        self.assertNotContains(response, record.description.replace("\n", "\\n"))
