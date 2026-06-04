import csv
import io

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import TestCase

from itsystems.models import ITSystemRecord, Status
from itsystems.utils import __validate_csv as validate
from itsystems.utils import export_csv, import_csv, get_user_related_systems

from .test_model import create_random_record


class UtilsTestCase(TestCase):
    class FauxCSVFile:
        def __init__(self, name, is_multiple_chunks, raw_text):
            self.raw_text = raw_text
            self.name = name
            self.is_multiple_chunks = is_multiple_chunks
            self.raw_text = raw_text

        def multiple_chunks(self):
            return self.is_multiple_chunks

        def read(self):
            return self

        def decode(self, encoding, errors):
            return self.raw_text

    class FauxPOST:
        def __init__(self, csv_file, user, force="False"):
            self.FILES = {"csv_file": csv_file}
            self.POST = {"force": force}
            self.user = user

    def setUp(self):
        create_random_record().save()
        create_random_record().save()

    def test_validate_csv(self):
        """
        Tests the file validation method __validate_csv().
        A file is valid if it's a csv, is under 2mb, and matches the required headers.
        """

        not_csv = UtilsTestCase.FauxCSVFile(name="test.txt", is_multiple_chunks=None, raw_text=None)
        above_2mb = UtilsTestCase.FauxCSVFile(name="test.csv", is_multiple_chunks=True, raw_text=None)

        incorrect_header_fields = ITSystemRecord._meta.get_fields()
        incorrect_csv_text = (",".join(get_field_names(incorrect_header_fields)) + "\r\n").replace("description", "non-existent-field")
        incorrect_headers = UtilsTestCase.FauxCSVFile(name="test.csv", is_multiple_chunks=False, raw_text=incorrect_csv_text)

        correct_header_fields = ITSystemRecord._meta.get_fields()[1:-4]
        csv_text = ",".join(get_field_names(correct_header_fields)) + "\r\nrandomtext"
        correct_headers = UtilsTestCase.FauxCSVFile(name="test.csv", is_multiple_chunks=False, raw_text=csv_text)

        self.assertIs(validate(not_csv)["valid"], False)
        self.assertIs(validate(above_2mb)["valid"], False)
        self.assertIs(validate(incorrect_headers)["valid"], False)
        self.assertIs(validate(correct_headers)["valid"], True)

    def test_export_csv(self):
        """
        Tests that all records exported by export_csv() accurately reflect existing records in the database.
        """
        faux_response = HttpResponse()
        export_csv(faux_response)
        raw_text = faux_response.content
        record_list = list(csv.DictReader(io.StringIO(raw_text.decode(encoding="utf-8", errors="replace"))))

        self.assertIs(len(record_list), len(ITSystemRecord.objects.all()))

        for record in record_list:
            try:
                found_record = ITSystemRecord.objects.get(system_id=record["system_id"])
            except:
                found_record = None

            self.assertIsNotNone(found_record)
            if found_record:
                new_record = ITSystemRecord()
                new_record.set_from_dict(record)
                changes = found_record.compare(new_record)
                self.assertIs(len(changes), 0)

    def test_import_csv(self):
        """
        Tests that all record import states in import_csv() are successfully and accurately reported
        """
        faux_user = User.objects.create_user(username="testuser", email="user@dbca.wa.gov.au", password="pass")

        # Validates that identical values do not trigger an update, deletion, or failure
        results = import_csv(get_faux_post(faux_user))
        original_size = len(ITSystemRecord.objects.all())
        self.assertEqual(len(results["created"]), 0)
        self.assertEqual(len(results["updated"]), 0)
        self.assertEqual(len(results["failed"]), 0)
        self.assertEqual(original_size, len(ITSystemRecord.objects.all()))

        # Validates update & creation results
        original_db = get_faux_post(faux_user)
        ITSystemRecord.objects.first().delete()
        record = ITSystemRecord.objects.first()
        new_description = str(record.description)
        old_description = str(record.description) + "new val"
        record.description = old_description
        record.save()
        original_size = len(ITSystemRecord.objects.all())
        results = import_csv(original_db)
        self.assertEqual(len(results["created"]), 1)
        self.assertEqual(len(results["updated"]), 1)
        self.assertEqual(results["updated"][0]["changes"][0]["field"], "description")
        self.assertEqual(results["updated"][0]["changes"][0]["old"], old_description)
        self.assertEqual(results["updated"][0]["changes"][0]["new"], new_description)
        system_id = results["updated"][0]["record"].split(" - ")[0].strip()
        self.assertEqual(ITSystemRecord.objects.get(system_id=system_id).description, new_description)
        self.assertEqual(len(results["failed"]), 0)
        self.assertEqual(original_size, len(ITSystemRecord.objects.all()) - 1)

        # Validates failure results by deleting required meta data 'user'
        original_db = get_faux_post(faux_user)
        ITSystemRecord.objects.first().delete()
        record = ITSystemRecord.objects.first()
        record.description = record.description + "new val"
        record.save()
        original_db.__delattr__("user")
        original_size = len(ITSystemRecord.objects.all())
        results = import_csv(original_db)
        self.assertEqual(len(results["created"]), 0)
        self.assertEqual(len(results["updated"]), 0)
        self.assertEqual(len(results["failed"]), 2)
        self.assertEqual(original_size, len(ITSystemRecord.objects.all()))

    def test_get_user_related_systems(self):
        """
        Tests that the systems and contact roles retrieved by get_user_related_systems() are accurate.
        """
        create_random_record().save()
        records = ITSystemRecord.objects.all()

        record1 = records.first()
        record2 = records.last()
        user1 = record1.technology_custodian
        old_user1 = record1.business_service_owner

        # Tests that a users related systems are accurately reported, and that their roles match
        # Singular role test
        user1_related_systems = get_user_related_systems(user1)
        self.assertEqual(len(user1_related_systems), 1)
        self.assertEqual(len(user1_related_systems[record1.system_id]), 1)
        self.assertEqual(list(user1_related_systems)[0], record1.system_id)
        self.assertEqual(user1_related_systems[record1.system_id][0], "technology_custodian")

        # Tests accurate reporting of a user with multiple roles within a singular system.
        # Also tests that users without any roles do not have any related systems reported
        record1.business_service_owner = user1
        record1.save()
        user1_related_systems = get_user_related_systems(user1)
        self.assertEqual(len(user1_related_systems), 1)
        self.assertEqual(list(user1_related_systems)[0], record1.system_id)
        self.assertEqual(len(user1_related_systems[record1.system_id]), 2)
        self.assertIn("technology_custodian", user1_related_systems[record1.system_id])
        self.assertIn("business_service_owner", user1_related_systems[record1.system_id])

        old_user1_related_systems = get_user_related_systems(old_user1)
        self.assertEqual(len(old_user1_related_systems), 0)

        # Tests that users with multiple roles across multiple systems are reported accurates.
        record2.information_custodian = user1
        record2.system_owner = user1
        record2.save()
        user1_related_systems = get_user_related_systems(user1)
        self.assertEqual(len(user1_related_systems), 2)
        self.assertEqual(len(user1_related_systems[record1.system_id]), 2)
        self.assertEqual(len(user1_related_systems[record2.system_id]), 2)
        self.assertIn("technology_custodian", user1_related_systems[record1.system_id])
        self.assertIn("business_service_owner", user1_related_systems[record1.system_id])
        self.assertIn("information_custodian", user1_related_systems[record2.system_id])
        self.assertIn("system_owner", user1_related_systems[record2.system_id])

        # Tests that if hide_decommissioned is true, decommissioned systems are hidden
        d_status = Status(name="Decommissioned")
        d_status.save()
        record1.status = d_status
        record1.save()
        user1_related_systems = get_user_related_systems(user1, hide_decommissioned=True)
        self.assertEqual(len(user1_related_systems), 1)
        self.assertIn(record2.system_id, user1_related_systems.keys())

        # Tests that if verbose_name is true, names become verbose
        user1_related_systems = get_user_related_systems(user1, verbose_names=True)
        self.assertEqual(len(user1_related_systems), 2)
        self.assertIn("Technology Custodian", user1_related_systems[record1.system_id])
        self.assertIn("Business Service Owner", user1_related_systems[record1.system_id])
        self.assertIn("Information Custodian", user1_related_systems[record2.system_id])
        self.assertIn("System Owner", user1_related_systems[record2.system_id])


def get_field_names(field_list):
    field_names = []
    for field in field_list:
        field_names.append(field.name)
    return field_names


def get_faux_post(user):
    faux_response = HttpResponse()
    export_csv(faux_response)
    faux_file = UtilsTestCase.FauxCSVFile(
        name="test.csv", is_multiple_chunks=False, raw_text=faux_response.content.decode(encoding="utf-8", errors="replace")
    )
    return UtilsTestCase.FauxPOST(faux_file, user)
