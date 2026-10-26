from django.urls import reverse

from itassets.test_api import ApiTestCase
from assets.tests.test_model import RandomAssetGenerator as Gen, RandomVulnGenerator as VGen
from assets.enum_library import Severity, SeverityMT, State
from itsystems.tests.test_model import create_random_record as gen_itsystem
from django.contrib.auth.models import Permission

import json
from datetime import datetime


class AssetsAPITestCase(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.asset1, self.asset2, self.asset3 = Gen().generate(3)
        self.asset1.save()
        self.asset2.save()
        self.asset3.save()

        # Gives permission for user to access API
        perm = Permission.objects.get(codename="view_asset")
        self.testuser.user_permissions.add(perm)
        self.testuser.save()

    def test_revoked_permissions(self):
        # Gives permission for user to access API
        perm = Permission.objects.get(codename="view_asset")
        self.testuser.user_permissions.remove(perm)
        self.testuser.save()

        url = reverse("asset_api_resource")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_populated(self):
        """
        Tests standard get call to assets endpoint, and data retrieval.
        """
        url = reverse("asset_api_resource")
        resp = self.client.get(url)
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

    def test_tenable_data_only(self):
        """
        Tests that tenable data is hidden and show appropriately depending on the flag.
        """
        self.asset1.tenable_data = {"test_tenable_data_key": "test_tenable_data_result"}
        self.asset1.save()

        # Confirms that the data is visible when flagged
        url = "{}?tenable_data_only".format(reverse("asset_api_resource"))
        resp = self.client.get(url)
        self.assertContains(resp, "test_tenable_data_key")
        self.assertContains(resp, "test_tenable_data_result")
        # Validates that it's exclusively showing the tenable data
        self.assertNotContains(resp, self.asset1.name)
        self.assertNotContains(resp, self.asset2.name)
        self.assertNotContains(resp, self.asset3.name)

        # Confirms that the data is hidden when not flagged
        url = reverse("asset_api_resource")
        resp = self.client.get(url)
        self.assertNotContains(resp, "test_tenable_data_key")
        self.assertNotContains(resp, "test_tenable_data_result")

    def test_filter_pk(self):
        """
        Tests filtering by PK
        """

        # Test pk found
        url = reverse("asset_api_resource", kwargs={"pk": self.asset1.pk})
        resp = self.client.get(url)
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
        self.assertContains(resp, self.asset1.name)

        # Test name not found
        url = reverse("asset_api_resource", query={"name": self.asset1.name + "FAKENAME"})
        resp = self.client.get(url)
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
        self.assertContains(resp, self.asset1.name)
        self.assertContains(resp, self.asset3.name)
        self.assertNotContains(resp, self.asset2.name)

        # Test tag cat not found
        url = reverse("asset_api_resource", query={"tag_cat": "tag_cat"})
        resp = self.client.get(url)
        self.assertNotContains(resp, self.asset1.name)
        self.assertNotContains(resp, self.asset2.name)
        self.assertNotContains(resp, self.asset3.name)

        # Test tag value found
        url = reverse("asset_api_resource", query={"tag": "tag_val"})
        resp = self.client.get(url)
        self.assertContains(resp, self.asset1.name)
        self.assertContains(resp, self.asset2.name)
        self.assertNotContains(resp, self.asset3.name)

        # Test tag value not found
        url = reverse("asset_api_resource", query={"tag": "tag"})
        resp = self.client.get(url)
        self.assertNotContains(resp, self.asset1.name)
        self.assertNotContains(resp, self.asset2.name)
        self.assertNotContains(resp, self.asset3.name)

        # Test tag value in tag cat found
        url = reverse("asset_api_resource", query={"tag": "tag_val", "tag_cat": "tag_cat_1"})
        resp = self.client.get(url)
        self.assertContains(resp, self.asset1.name)
        self.assertNotContains(resp, self.asset2.name)
        self.assertNotContains(resp, self.asset3.name)

        # Test tag val found, but not cat
        url = reverse("asset_api_resource", query={"tag": "tag_val", "tag_cat": "tag"})
        resp = self.client.get(url)
        self.assertNotContains(resp, self.asset1.name)
        self.assertNotContains(resp, self.asset2.name)
        self.assertNotContains(resp, self.asset3.name)

        # Test tag cat found, but not tag val
        url = reverse("asset_api_resource", query={"tag": "tag", "tag_cat": "tag_cat_1"})
        resp = self.client.get(url)
        self.assertNotContains(resp, self.asset1.name)
        self.assertNotContains(resp, self.asset2.name)
        self.assertNotContains(resp, self.asset3.name)

        # Test assert none found
        url = reverse("asset_api_resource", query={"tag": "tag", "tag_cat": "tag"})
        resp = self.client.get(url)
        self.assertNotContains(resp, self.asset1.name)
        self.assertNotContains(resp, self.asset2.name)
        self.assertNotContains(resp, self.asset3.name)


class VulnerabilityAPITestCase(ApiTestCase):
    def setUp(self):
        super().setUp()
        # Data set:
        # - Asset with singular vuln
        # - Asset with multiple vulns
        # - Asset with singular vuln and singular it system
        # - Asset with multiple vulns and multiple it systems

        # Generate 2 IT Systems
        self.itsystem_1 = gen_itsystem()
        self.itsystem_2 = gen_itsystem()

        # Generate 4 Assets
        self.asset_vuln, self.asset_vulns, self.asset_vuln_and_system, self.asset_vulns_and_systems = Gen().generate(4)
        self.asset_vuln_and_system.systems.add(self.itsystem_1)
        self.asset_vuln_and_system.save()
        self.asset_vulns_and_systems.systems.set([self.itsystem_1, self.itsystem_2])
        self.asset_vulns_and_systems.save()

        # attach vulns to assets of various severities
        vgen = VGen()
        (self.a_high_vuln,) = vgen.generate(self.asset_vuln, 1)
        (self.b_critical_vuln,) = vgen.generate(self.asset_vuln_and_system, 1)
        self.c_info_vuln, self.c_low_vuln, self.c_medium_vuln, self.c_high_vuln, self.c_critical_vuln = vgen.generate(self.asset_vulns, 5)
        self.d_info_vuln, self.d_low_vuln, self.d_medium_vuln, self.d_high_vuln, self.d_critical_vuln = vgen.generate(
            self.asset_vulns_and_systems, 5
        )

        # Severity, state, and  Setting
        def set_vuln(vuln, sev: int, sev_mt: str, state: str):
            vuln.severity = sev
            vuln.severity_modification_type = sev_mt
            vuln.state = state
            vuln.save()

        set_vuln(self.a_high_vuln, Severity.HIGH, SeverityMT.NONE, State.OPEN)
        set_vuln(self.b_critical_vuln, Severity.CRITICAL, SeverityMT.NONE, State.OPEN)
        set_vuln(self.c_info_vuln, Severity.INFO, SeverityMT.NONE, State.OPEN)
        set_vuln(self.c_low_vuln, Severity.LOW, SeverityMT.NONE, State.REOPENED)
        set_vuln(self.c_medium_vuln, Severity.MEDIUM, SeverityMT.NONE, State.OPEN)
        set_vuln(self.c_high_vuln, Severity.HIGH, SeverityMT.NONE, State.OPEN)
        set_vuln(self.c_critical_vuln, Severity.CRITICAL, SeverityMT.RECASTED, State.OPEN)
        set_vuln(self.d_info_vuln, Severity.INFO, SeverityMT.NONE, State.OPEN)
        set_vuln(self.d_low_vuln, Severity.LOW, SeverityMT.NONE, State.REOPENED)
        set_vuln(self.d_medium_vuln, Severity.MEDIUM, SeverityMT.NONE, State.OPEN)
        set_vuln(self.d_high_vuln, Severity.HIGH, SeverityMT.NONE, State.OPEN)
        set_vuln(self.d_critical_vuln, Severity.CRITICAL, SeverityMT.RECASTED, State.OPEN)

        # Gives permission for user to access API
        perm = Permission.objects.get(codename="view_vulnerability")
        self.testuser.user_permissions.add(perm)
        self.testuser.save()

    def test_revoked_permissions(self):
        # revokes permission for user to access API
        perm = Permission.objects.get(codename="view_vulnerability")
        self.testuser.user_permissions.remove(perm)
        self.testuser.save()

        url = reverse("asset_api_resource")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_populated(self):
        """
        Tests standard get call to vuln endpoint, and data retrieval.
        Validates that all vulns are returned by default.
        """
        url = reverse("vulnerability_api_resource")
        resp = self.client.get(url)
        self.assertContains(resp, self.a_high_vuln.finding_id)
        self.assertContains(resp, self.b_critical_vuln.finding_id)
        self.assertContains(resp, self.c_low_vuln.finding_id)
        self.assertContains(resp, self.c_medium_vuln.finding_id)
        self.assertContains(resp, self.c_high_vuln.finding_id)
        self.assertContains(resp, self.c_critical_vuln.finding_id)
        self.assertContains(resp, self.d_low_vuln.finding_id)
        self.assertContains(resp, self.d_medium_vuln.finding_id)
        self.assertContains(resp, self.d_high_vuln.finding_id)
        self.assertContains(resp, self.d_critical_vuln.finding_id)
        self.assertContains(resp, self.asset_vuln.name)
        self.assertContains(resp, self.asset_vulns.name)
        self.assertContains(resp, self.asset_vuln_and_system.name)
        self.assertContains(resp, self.asset_vulns_and_systems.name)
        self.assertContains(resp, self.c_info_vuln.finding_id)
        self.assertContains(resp, self.d_info_vuln.finding_id)

        content = json.loads(resp.content)
        self.assertEqual(len(content), 12)

    def test_severity_filter(self):
        """
        Validates that the severity filter works
        """

        # standard filtering
        url = reverse("vulnerability_api_resource", query={"severity": "INFO"})
        resp = self.client.get(url)
        self.assertContains(resp, self.c_info_vuln.finding_id)
        self.assertContains(resp, self.d_info_vuln.finding_id)
        content = json.loads(resp.content)
        self.assertEqual(len(content), 2)

        # exclusion filter
        url = reverse("vulnerability_api_resource", query={"severity": "NOT_MEDIUM"})
        resp = self.client.get(url)
        self.assertNotContains(resp, self.c_medium_vuln.finding_id)
        self.assertNotContains(resp, self.d_medium_vuln.finding_id)
        content = json.loads(resp.content)
        self.assertEqual(len(content), 10)

        # greater than filter
        url = reverse("vulnerability_api_resource", query={"severity": "GT_LOW"})
        resp = self.client.get(url)
        self.assertNotContains(resp, self.c_info_vuln.finding_id)
        self.assertNotContains(resp, self.d_info_vuln.finding_id)
        self.assertNotContains(resp, self.c_low_vuln.finding_id)
        self.assertNotContains(resp, self.d_low_vuln.finding_id)
        content = json.loads(resp.content)
        self.assertEqual(len(content), 8)

        # Non existent severity filter
        url = reverse("vulnerability_api_resource", query={"severity": "SOMETHING_FAKE"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(0, len(json.loads(resp.content)))

        url = reverse("vulnerability_api_resource", query={"severity": "NOT_REAL"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(0, len(json.loads(resp.content)))

        url = reverse("vulnerability_api_resource", query={"severity": "GT_NOTHING"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(0, len(json.loads(resp.content)))

    def test_severity_mod_type_filter(self):
        """
        Validates that the severity mod type filter works
        """

        # standard filtering
        url = reverse("vulnerability_api_resource", query={"severity_mod_type": "RECASTED"})
        resp = self.client.get(url)
        self.assertContains(resp, self.c_critical_vuln)
        self.assertContains(resp, self.d_critical_vuln)
        content = json.loads(resp.content)
        self.assertEqual(len(content), 2)

        # exclusion filter
        url = reverse("vulnerability_api_resource", query={"severity_mod_type": "NOT_RECASTED"})
        resp = self.client.get(url)
        self.assertNotContains(resp, self.c_critical_vuln.finding_id)
        self.assertNotContains(resp, self.d_critical_vuln.finding_id)
        self.assertEqual(10, len(json.loads(resp.content)))

        # Non existent severity mod type filter
        url = reverse("vulnerability_api_resource", query={"severity_mod_type": "SOMETHING_FAKE"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(0, len(json.loads(resp.content)))

        url = reverse("vulnerability_api_resource", query={"severity_mod_type": "NOT_REAL"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(0, len(json.loads(resp.content)))

    def test_state_filter(self):
        """
        Validates that the severity filter works
        """

        # standard filtering
        url = reverse("vulnerability_api_resource", query={"state": "REOPENED"})
        resp = self.client.get(url)
        self.assertContains(resp, self.c_low_vuln)
        self.assertContains(resp, self.d_low_vuln)
        content = json.loads(resp.content)
        self.assertEqual(len(content), 2)

        # exclusion filter
        url = reverse("vulnerability_api_resource", query={"state": "NOT_REOPENED"})
        resp = self.client.get(url)
        self.assertNotContains(resp, self.c_low_vuln.finding_id)
        self.assertNotContains(resp, self.d_low_vuln.finding_id)
        self.assertEqual(10, len(json.loads(resp.content)))

        # Non existent state filter
        url = reverse("vulnerability_api_resource", query={"state": "SOMETHING_FAKE"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(0, len(json.loads(resp.content)))

        url = reverse("vulnerability_api_resource", query={"state": "NOT_REAL"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(0, len(json.loads(resp.content)))

    def test_asset_filter(self):
        """
        Tests that vulns can be accurately filtered by their asset
        """
        # singular vuln test
        url = reverse("vulnerability_api_resource", query={"asset": self.asset_vuln.name})
        resp = self.client.get(url)
        self.assertContains(resp, self.a_high_vuln.finding_id)
        self.assertEqual(1, len(json.loads(resp.content)))

        # multi vuln test
        url = reverse("vulnerability_api_resource", query={"asset": self.asset_vulns.name})
        resp = self.client.get(url)
        self.assertContains(resp, self.c_info_vuln.finding_id)
        self.assertContains(resp, self.c_low_vuln.finding_id)
        self.assertContains(resp, self.c_medium_vuln.finding_id)
        self.assertContains(resp, self.c_high_vuln.finding_id)
        self.assertContains(resp, self.c_critical_vuln.finding_id)
        self.assertEqual(5, len(json.loads(resp.content)))

        # non-existent asset test
        url = reverse("vulnerability_api_resource", query={"asset": self.asset_vulns.name + "FAKE_VULN"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(0, len(json.loads(resp.content)))

    def test_it_system_filter(self):
        """
        Tests that vulns can be accurately filtered by their assets related it system
        """
        url = reverse("vulnerability_api_resource", query={"it_system": self.itsystem_2.system_id})
        resp = self.client.get(url)

        # Test that only related vulnerabilities are found: Vulns for asset "asset_vulns_and_systems"
        self.assertContains(resp, self.d_info_vuln.finding_id)
        self.assertContains(resp, self.d_low_vuln.finding_id)
        self.assertContains(resp, self.d_medium_vuln.finding_id)
        self.assertContains(resp, self.d_high_vuln.finding_id)
        self.assertContains(resp, self.d_critical_vuln.finding_id)
        self.assertEqual(5, len(json.loads(resp.content)))

        url = reverse("vulnerability_api_resource", query={"it_system": self.itsystem_1.system_id})
        resp = self.client.get(url)

        # Test that only related vulnerabilities are found: Vulns for assets "asset_vulns_and_systems" and "asset_vuln_and_system"
        self.assertContains(resp, self.b_critical_vuln.finding_id)
        self.assertContains(resp, self.d_info_vuln.finding_id)
        self.assertContains(resp, self.d_low_vuln.finding_id)
        self.assertContains(resp, self.d_medium_vuln.finding_id)
        self.assertContains(resp, self.d_high_vuln.finding_id)
        self.assertContains(resp, self.d_critical_vuln.finding_id)
        self.assertEqual(6, len(json.loads(resp.content)))

        # non-existent it-system test
        url = reverse("vulnerability_api_resource", query={"asset": self.itsystem_1.system_id + "FAKE_SYS"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(0, len(json.loads(resp.content)))

    def test_finding_id_filter(self):
        """
        Tests that the finding_id filter works
        """
        # Test finding_id found
        url = reverse("vulnerability_api_resource", kwargs={"finding_id": self.d_critical_vuln.finding_id})
        resp = self.client.get(url)
        self.assertContains(resp, self.d_critical_vuln.finding_id)
        self.assertEqual(1, len(json.loads(resp.content)))

        # Test non-existent finding_id
        url = reverse("vulnerability_api_resource", kwargs={"finding_id": self.d_critical_vuln.finding_id + "FAKE_STUFF"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(0, len(json.loads(resp.content)))

    def test_fields_flags(self):
        """
        Tests that the field flags "tenable_data_only" and "expanded_fields" show the correct data
        """

        # Validates that the "tenable_data_only" flag only shows tenable data
        self.d_critical_vuln.raw_vuln_data = {"TEST_RAW_TENABLE_DATA_KEY": "TEST_RAW_TENABLE_DATA_VALUE"}
        self.d_critical_vuln.save()
        url = reverse("vulnerability_api_resource", query={"tenable_data_only": ""}, kwargs={"finding_id": self.d_critical_vuln.finding_id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.d_critical_vuln.raw_vuln_data, json.loads(resp.content)[0])
        self.assertNotContains(resp, "age_in_days")  # this field is unique to other field sets

        # Validates that without the flags, none of the extra data is present
        url = reverse("vulnerability_api_resource", kwargs={"finding_id": self.d_critical_vuln.finding_id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        d = json.loads(resp.content)[0]
        # standard fields
        self.assertContains(resp, self.d_critical_vuln.finding_id)
        self.assertContains(resp, self.d_critical_vuln.asset_name)
        self.assertContains(resp, self.d_critical_vuln.get_state_display())
        self.assertContains(resp, self.d_critical_vuln.get_severity_display())
        self.assertEqual(datetime.fromisoformat(d["first_found"]), self.d_critical_vuln.first_found)
        self.assertEqual(datetime.fromisoformat(d["last_found"]), self.d_critical_vuln.last_found)
        self.assertContains(resp, self.d_critical_vuln.age_in_days)
        self.assertContains(resp, self.d_critical_vuln.plugin_name)
        self.assertContains(resp, self.d_critical_vuln.plugin_family)
        self.assertContains(resp, self.d_critical_vuln.plugin_output)
        self.assertContains(resp, self.d_critical_vuln.plugin_description)
        self.assertContains(resp, self.d_critical_vuln.solution)
        self.assertEqual(d["output"], self.d_critical_vuln.output)
        self.assertContains(resp, str(self.d_critical_vuln.exploited_by_malware).lower())
        self.assertContains(resp, str(self.d_critical_vuln.exploited_by_nessus).lower())
        self.assertContains(resp, str(self.d_critical_vuln.has_patch).lower())
        self.assertContains(resp, self.d_critical_vuln.patch_publication_date)
        self.assertContains(resp, self.d_critical_vuln.cvss3_base_score)
        # expanded fields
        self.assertIsNone(d.get("last_fixed"))
        self.assertIsNone(d.get("indexed"))
        self.assertIsNone(d.get("source"))
        self.assertIsNone(d.get("resurfaced_date"))
        self.assertIsNone(d.get("time_taken_to_fix"))
        self.assertIsNone(d.get("cve"))
        self.assertIsNone(d.get("workaround"))
        # raw tenable data
        self.assertNotContains(resp, self.d_critical_vuln.raw_vuln_data)

        # Validates that the "expanded_fields" flag provides the additional fields
        url = reverse(
            "vulnerability_api_resource", query={"expanded_fields": "test"}, kwargs={"finding_id": self.d_critical_vuln.finding_id}
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        d = json.loads(resp.content)[0]
        # standard fields
        self.assertContains(resp, self.d_critical_vuln.finding_id)
        self.assertContains(resp, self.d_critical_vuln.asset_name)
        self.assertContains(resp, self.d_critical_vuln.get_state_display())
        self.assertContains(resp, self.d_critical_vuln.get_severity_display())
        self.assertEqual(datetime.fromisoformat(d["first_found"]), self.d_critical_vuln.first_found)
        self.assertEqual(datetime.fromisoformat(d["last_found"]), self.d_critical_vuln.last_found)
        self.assertContains(resp, self.d_critical_vuln.age_in_days)
        self.assertContains(resp, self.d_critical_vuln.plugin_name)
        self.assertContains(resp, self.d_critical_vuln.plugin_family)
        self.assertContains(resp, self.d_critical_vuln.plugin_output)
        self.assertContains(resp, self.d_critical_vuln.plugin_description)
        self.assertContains(resp, self.d_critical_vuln.solution)
        self.assertEqual(d["output"], self.d_critical_vuln.output)
        self.assertContains(resp, str(self.d_critical_vuln.exploited_by_malware).lower())
        self.assertContains(resp, str(self.d_critical_vuln.exploited_by_nessus).lower())
        self.assertContains(resp, str(self.d_critical_vuln.has_patch).lower())
        self.assertContains(resp, self.d_critical_vuln.patch_publication_date)
        self.assertContains(resp, self.d_critical_vuln.cvss3_base_score)
        # additional fields
        self.assertEqual(datetime.fromisoformat(d["last_fixed"]), self.d_critical_vuln.last_fixed)
        self.assertEqual(datetime.fromisoformat(d["indexed"]), self.d_critical_vuln.indexed)
        self.assertContains(resp, self.d_critical_vuln.source)
        self.assertEqual(datetime.fromisoformat(d["resurfaced_date"]).date(), self.d_critical_vuln.resurfaced_date)
        self.assertContains(resp, self.d_critical_vuln.time_taken_to_fix)
        self.assertContains(resp, self.d_critical_vuln.cve)
        self.assertContains(resp, self.d_critical_vuln.workaround)
        # raw tenable data
        self.assertNotContains(resp, self.d_critical_vuln.raw_vuln_data)

    def test_multi_filters_test(self):
        """
        Tests that all filters work accurately in combination
        """
        url = reverse(
            "vulnerability_api_resource",
            query={
                "state": "NOT_REOPENED",
                "severity": "GT_INFO",
                "severity_mod_type": "NOT_RECASTED",
                "asset": self.asset_vulns_and_systems.name,
            },
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        d = json.loads(resp.content)

        # should only contain 2 records
        self.assertEqual(2, len(d))
        self.assertContains(resp, self.d_high_vuln.finding_id)
        self.assertContains(resp, self.d_medium_vuln.finding_id)

        url = reverse(
            "vulnerability_api_resource",
            query={
                "state": "NOT_REOPENED",
                "severity": "GT_INFO",
                "severity_mod_type": "NOT_RECASTED",
                "it_system": self.itsystem_2.system_id,
            },
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        d = json.loads(resp.content)

        # should only contain the same 2 records
        self.assertEqual(2, len(d))
        self.assertContains(resp, self.d_high_vuln.finding_id)
        self.assertContains(resp, self.d_medium_vuln.finding_id)
