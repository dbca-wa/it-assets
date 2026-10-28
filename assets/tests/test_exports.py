from django.http import HttpResponse
from django.test import TestCase

from assets.exports import export_asset_vulns, export_vulns
from assets.tests.test_model import RandomAssetGenerator as Gen, RandomVulnGenerator as VGen
from assets.enum_library import Severity, SeverityMT, State
from itsystems.tests.test_model import create_random_record as gen_itsystem
from assets.models import Vulnerability, Asset

from datetime import datetime

import csv
import io

class ExportsTestCase(TestCase):
    def setUp(self):
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
        self.asset_vuln.systems.clear()
        self.asset_vulns.systems.clear()

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

        self.vuln_list = [
            self.a_high_vuln,
            self.b_critical_vuln,
            self.c_info_vuln,
            self.c_low_vuln,
            self.c_medium_vuln,
            self.c_high_vuln,
            self.c_critical_vuln,
            self.d_info_vuln,
            self.d_low_vuln,
            self.d_medium_vuln,
            self.d_high_vuln,
            self.d_critical_vuln
        ]

        # Loads up vuln stats
        self.asset_vuln._Asset__refresh_vuln_stats()
        self.asset_vulns._Asset__refresh_vuln_stats()
        self.asset_vuln_and_system._Asset__refresh_vuln_stats()
        self.asset_vulns_and_systems._Asset__refresh_vuln_stats()

        # Add assets & vulns to accessible lists
        self.asset_list = [
            self.asset_vuln,
            self.asset_vulns,
            self.asset_vuln_and_system,
            self.asset_vulns_and_systems,
        ]

        for asset in self.asset_list:
            asset.save()

    def dict_list_conv(self, content: bytes) -> list[dict]:
        return list(csv.DictReader(io.StringIO(content.decode(encoding="utf-8", errors="replace"))))

    def assert_all_vulns_present_and_correct(self, csv_list: list[dict], verification_list: list[Vulnerability], include_it_system: bool = False, simple: bool=True):
        found_vulns = set()

        for vuln in csv_list:
            asset_col = "Asset" if simple else "ASSET"
            plugin_name_col = "Type" if simple else "PLUGIN_NAME"

            found_asset = Asset.objects.filter(name = vuln[asset_col])
            self.assertTrue(found_asset.exists())
            found_asset = found_asset.first()
            found_vuln = Vulnerability.objects.filter(plugin__name = vuln[plugin_name_col])
            self.assertTrue(found_vuln.exists())
            found_vuln = found_vuln.first()

            # append to list
            found_vulns.add(found_vuln.pk)

            # assert that every item found was also in the verification list
            self.assertIn(found_vuln, verification_list)

            # Assert contents match
            if simple:
                if include_it_system:
                    self.assertEqual(found_asset.associated_systems, vuln["IT System"])
                self.assertEqual(found_vuln.get_severity_display(), vuln["Severity"])
                self.assertEqual(found_vuln.plugin_output, vuln["Problem"])
                self.assertEqual(found_vuln.solution, vuln["Solution"])
                self.assertEqual(found_vuln.plugin_description, vuln["Full Problem"])
                self.assertEqual(found_vuln.output, vuln["Technical Info"])
            else:
                if include_it_system:
                    self.assertEqual(found_asset.associated_systems, vuln["IT_SYSTEMS"])
                self.assertEqual(found_vuln.asset_name, vuln["ASSET"])
                self.assertEqual(found_vuln.finding_id, vuln["FINDING_ID"])
                self.assertEqual(found_vuln.get_state_display(), vuln["STATE"])
                self.assertEqual(found_vuln.get_severity_display(), vuln["SEVERITY"])
                self.assertEqual(found_vuln.get_severity_modification_type_display(), vuln["SEVERITY_MODIFICATION_TYPE"])
                self.assertEqual(found_vuln.output, vuln["OUTPUT"])
                self.assertEqual(found_vuln.first_found, datetime.fromisoformat(vuln["FIRST_FOUND"]))
                self.assertEqual(found_vuln.last_found, datetime.fromisoformat(vuln["LAST_FOUND"]))
                self.assertEqual(found_vuln.last_fixed, datetime.fromisoformat(vuln["LAST_FIXED"]))
                self.assertEqual(found_vuln.source, vuln["SOURCE"])
                self.assertEqual(found_vuln.resurfaced_date, datetime.fromisoformat(vuln["RESURFACED_DATE"]).date())
                self.assertEqual(str(found_vuln.time_taken_to_fix), vuln["TIME_TAKEN_TO_FIX"])
                self.assertEqual(found_vuln.plugin_id, vuln["PLUGIN_ID"])
                self.assertEqual(found_vuln.plugin_name, vuln["PLUGIN_NAME"])
                self.assertEqual(found_vuln.plugin_family, vuln["PLUGIN_FAMILY"])
                self.assertEqual(found_vuln.vuln_age, vuln["VULN_AGE"])
                self.assertEqual(found_vuln.plugin_output, vuln["PLUGIN_OUTPUT"])
                self.assertEqual(found_vuln.plugin_description, vuln["PLUGIN_DESCRIPTION"])
                self.assertEqual(found_vuln.solution, vuln["SOLUTION"])
                self.assertEqual(str(found_vuln.has_patch), vuln["HAS_PATCH"])
                self.assertEqual(found_vuln.patch_publication_date, datetime.fromisoformat(vuln["PATCH_PUBLICATION_DATE"]).date())
                self.assertEqual(str(found_vuln.exploitability_ease), vuln["EXPLOITABILITY_EASE"])
                self.assertEqual(str(found_vuln.exploited_by_malware), vuln["EXPLOITED_BY_MALWARE"])
                self.assertEqual(str(found_vuln.exploited_by_nessus), vuln["EXPLOITED_BY_NESSUS"])
                self.assertEqual(found_vuln.cvss3_base_score, float(vuln["CVSS3_BASE_SCORE"]))
                self.assertEqual(found_vuln.cve, vuln["CVE"])
                self.assertEqual(found_vuln.workaround, vuln["WORKAROUND"])

        for vuln in verification_list:
            self.assertIn(vuln.pk,found_vulns)

    def test_simple_vuln_export(self):
        """
        Tests a standard simple vulnerability export, and ensures that all fields are accurately written to the csv
        """
        resp = export_vulns(response = HttpResponse(),vulns=self.vuln_list, simple=True)
        csv_list = self.dict_list_conv(resp.content) 

        self.assert_all_vulns_present_and_correct(csv_list,self.vuln_list, simple=True)

    def test_technical_vuln_export(self):
        """
        Tests a standard tecnical vulnerability export, and ensures that all fields are accurately written to the csv
        """
        resp = export_vulns(response = HttpResponse(),vulns=self.vuln_list, simple=False)
        csv_list = self.dict_list_conv(resp.content) 

        self.assert_all_vulns_present_and_correct(csv_list,self.vuln_list, simple=False)

    def test_simple_asset_vuln_export(self):
        """
        Tests a standard simple asset vulnerability export, and ensures that all fields are accurately written to the csv.
        """
        resp = export_asset_vulns(response = HttpResponse(),assets=self.asset_list, simple=True)
        csv_list = self.dict_list_conv(resp.content) 

        # Verifies all present, and automatic info levele vuln exclusion
        verification_list = list(Vulnerability.objects.exclude(severity=Severity.INFO))
        self.assert_all_vulns_present_and_correct(csv_list,verification_list, include_it_system=True, simple=True)

    def test_simple_asset_vuln_export_filters(self):
        """
        Tests performing a simple asset vuln export, but with a severity filter.
        Verifies that only assets outside of the excluded severities will be exported.
        """
        resp = export_asset_vulns(response = HttpResponse(),assets=self.asset_list,severity_exclude_list=[Severity.MEDIUM,Severity.HIGH], simple=True)
        csv_list = self.dict_list_conv(resp.content) 

        verification_list = list(Vulnerability.objects.exclude(severity__in=[Severity.INFO,Severity.MEDIUM, Severity.HIGH]))
        self.assert_all_vulns_present_and_correct(csv_list,verification_list, include_it_system=True, simple=True)

    def test_technical_asset_vuln_export(self):
        """
        Tests a standard technical asset vulnerability export, and ensures that all fields are accurately written to the csv.
        """
        resp = export_asset_vulns(response = HttpResponse(),assets=self.asset_list, simple=False)
        csv_list = self.dict_list_conv(resp.content) 

        # Verifies all present, and automatic info levele vuln exclusion
        verification_list = list(Vulnerability.objects.exclude(severity=Severity.INFO))
        self.assert_all_vulns_present_and_correct(csv_list,verification_list, include_it_system=False, simple=False)

    def test_technical_asset_vuln_export_filters(self):
        """
        Tests performing a technical asset vuln export, but with a severity filter.
        Verifies that only assets outside of the excluded severities will be exported.
        """
        resp = export_asset_vulns(response = HttpResponse(),assets=self.asset_list,severity_exclude_list=[Severity.LOW,Severity.CRITICAL], simple=False)
        csv_list = self.dict_list_conv(resp.content) 

        verification_list = list(Vulnerability.objects.exclude(severity__in=[Severity.INFO,Severity.LOW, Severity.CRITICAL]))
        self.assert_all_vulns_present_and_correct(csv_list,verification_list, include_it_system=True, simple=False)