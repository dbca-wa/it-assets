from django.test import TestCase, override_settings
from mixer.backend.django import mixer
from uuid import uuid1

from itsystems.models import ITSystemRecord, Division
from organisation.models import DepartmentUser
from organisation.tests.test_models import random_string
from itassets.test_api import random_dbca_email


class ITSystemRecordTestCase(TestCase):
    def setUp(self):
        self.record = create_random_record()

    def test_compare(self):
        """
        Tests the ITSystemRecord method Compare().
        compare() returns a list of differences between itself and in imported model.
        If the list is empty, it's identical outside of meta-data and the primary key.
        """

        # Creates duplicate record
        copied_record = duplicate_record(self.record)

        # Creates completely random record, ensuring it can't accidentally generate the same vals for non-unique.
        diff_record_1 = create_random_record()
        diff_record_1.name = self.record.description + random_string()
        diff_record_1.description = self.record.description + random_string()

        # Creates record with 1 difference
        diff_record_2 = duplicate_record(self.record)
        diff_record_2.description = self.record.description + " with extra text"

        no_changes = self.record.compare(copied_record)
        all_changes = self.record.compare(diff_record_1)
        single_change = self.record.compare(diff_record_2)

        # asserts that identical records do not have any reported changes
        self.assertIs(len(no_changes), 0)

        # asserts that a singular change is accurately reported in the change log
        self.assertIs(len(single_change), 1)
        self.assertIs(single_change[0]["new"], diff_record_2.description)
        self.assertIs(single_change[0]["old"], self.record.description)

        # asserts multiple changes are accurately reported in the change log
        self.assertIs(len(all_changes), 7)
        for change in all_changes:
            old_val = str(getattr(self.record, change["field"]))
            new_val = str(getattr(diff_record_1, change["field"]))
            self.assertIs(change["old"], old_val)
            self.assertIs(change["new"], new_val)
            self.assertIs(old_val == new_val, False)

    def test_set_from_dict(self):
        """
        Tests the ITSystemRecord method override_from_dict().
        Ensures that the function can successfully overrite a record if the imported dict is a direct copy of a record or converted to plain text for fk & bool variables.
        """
        record = create_random_record()
        new_record = ITSystemRecord()
        record_dict = get_record_dict(record)
        new_record.set_from_dict(record_dict, plain_text=False)

        # Test standard full replacement
        changes = record.compare(new_record)
        self.assertIs(len(changes), 0)

        # Testing standard override 1 field
        record_dict["name"] = record.name + random_string()
        new_record.set_from_dict(record_dict, plain_text=False)
        changes = record.compare(new_record)
        self.assertIs(len(changes), 1)

        # test plain text full replacement
        new_record = ITSystemRecord()
        record_dict = get_record_dict(record)
        record_dict["system_owner"] = record.system_owner.email
        record_dict["business_service_owner"] = record.business_service_owner.email
        record_dict["technology_custodian"] = record.technology_custodian.email
        record_dict["information_custodian"] = record.information_custodian.email
        record_dict["division"] = record.division.name
        record_dict["status"] = record.status.name
        record_dict["availability"] = record.availability.name
        record_dict["seasonality"] = record.seasonality.name
        record_dict["sensitivity"] = record.sensitivity.name
        record_dict["system_type"] = record.system_type.name
        record_dict["vital_records"] = str(record.vital_records)
        new_record.set_from_dict(record_dict, plain_text=True)
        changes = record.compare(new_record)
        self.assertIs(len(changes), 0)

    @override_settings(IT_SYSTEMS_REGISTER_EMAIL="invalid_email")  # prevents sending emails during tests
    def test_null_on_delete(self):
        """
        Tests the ITSystemRecord SET_NULL_AND_NOTIFY delete function sets contact fields to null upon the fk objects deletion.
        Overrides the target email address for notifications so that this doesn't cause an email address to be sent.
        """
        pk = self.record.business_service_owner.pk
        user = DepartmentUser.objects.get(pk=pk)
        user.delete()
        updated_record = ITSystemRecord.objects.get(pk=self.record.pk)
        self.assertEqual(updated_record.business_service_owner, None)


# Creates a DepartmentUser object for testing
def create_test_user():
    return mixer.blend(
        DepartmentUser,
        active=True,
        email=random_dbca_email,
        given_name=mixer.RANDOM,
        surname=mixer.RANDOM,
        employee_id=mixer.RANDOM,
        dir_sync_enabled=True,
        ad_data={"DistinguishedName": random_string()},
        azure_guid=uuid1,
    )


# Creates a random Division object for testing
def create_test_division():
    return mixer.blend(Division, name=mixer.RANDOM)


# Creates a random ITSystemRecord object for testing
def create_random_record():
    return mixer.blend(
        ITSystemRecord,
        system_id=mixer.RANDOM,
        name=mixer.RANDOM,
        division=create_test_division(),
        description=mixer.RANDOM,
        business_service_owner=create_test_user(),
        system_owner=create_test_user(),
        technology_custodian=create_test_user(),
        information_custodian=create_test_user(),
    )


# Duplicates an ITSystemRecord object for testing
def duplicate_record(record):
    return mixer.blend(
        ITSystemRecord,
        system_id=record.system_id + random_string(),
        name=record.name,
        division=record.division,
        description=record.description,
        business_service_owner=record.business_service_owner,
        system_owner=record.system_owner,
        technology_custodian=record.technology_custodian,
        information_custodian=record.information_custodian,
    )


# Gets the dictionary of an ITSystemRecord object
def get_record_dict(record):
    dict = record.__dict__.copy()
    excluded_fields = ["created_date", "modified_date", "created_by", "modified_by", "id", "_state"]
    for field in excluded_fields:
        if field in dict:
            del dict[field]
    return dict
