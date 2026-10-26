from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from mixer.backend.django import mixer
from django.urls import reverse

from assets.tests.test_model import RandomAssetGenerator as Gen, RandomVulnGenerator as VGen
from assets.enum_library import Severity, SeverityMT, State
from itsystems.tests.test_model import create_random_record as gen_itsystem


User = get_user_model()


class VulnerabilityAdminTestCase(TestCase):
    def setUp(self):
        super(VulnerabilityAdminTestCase, self).setUp()
        # Create & log in an admin user.
        self.admin_user = mixer.blend(User, username="admin", is_superuser=True, is_staff=True)
        self.admin_user.set_password("pass")
        self.admin_user.save()
        self.client.login(username="admin", password="pass")

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

    def assert_contains_only(self, resp, exception_list):
        """
        Asserts that response only contains the vulns in the exception list
        """
        for vuln in self.vuln_list:
            if vuln in exception_list:
                self.assertContains(resp,vuln.plugin_name)
            else:
                self.assertNotContains(resp, vuln.plugin_name)

    def assert_contains_all_except(self,resp, exclusion_list):
        """
        Asserts that response doesn't contain the vulns in the exclusion list
        """
        for vuln in self.vuln_list:
            if vuln in exclusion_list:
                self.assertNotContains(resp,vuln.plugin_name)
            else:
                self.assertContains(resp, vuln.plugin_name)

    def assert_contains_none(self, resp):
        """
        Asserts that response didn't contain any vulns
        """
        for vuln in self.vuln_list:
            self.assertNotContains(resp, vuln.plugin_name)

    def assert_contains_all(self, resp):
        """
        Asserts that response contained all vulns
        """
        for vuln in self.vuln_list:
            self.assertContains(resp, vuln.plugin_name)

    def test_populated(self):
        """Test the customised Vulnerability admin view"""
        url = reverse("service_desk_admin:assets_vulnerability_changelist")
        resp = self.client.get(url)
        self.assert_contains_all(resp)
        self.assertContains(resp, self.asset_vuln.name)
        self.assertContains(resp, self.asset_vulns.name)
        self.assertContains(resp, self.asset_vuln_and_system.name)
        self.assertContains(resp, self.asset_vulns_and_systems.name)

    def test_severity_filter(self):
        """
        Validates that the severity filter works
        """

        # standard filtering
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"severity": f"{Severity.INFO}"})
        resp = self.client.get(url)
        self.assert_contains_only(resp, [self.c_info_vuln, self.d_info_vuln])

        # greater than filter
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"severity": f"GT_{Severity.MEDIUM}"})
        resp = self.client.get(url)
        self.assert_contains_only(resp, [
            self.a_high_vuln, 
            self.c_high_vuln,
            self.d_high_vuln,
            self.b_critical_vuln,
            self.c_critical_vuln,
            self.d_critical_vuln,
            ])

        # Non existent severity filter
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"severity": "999999"})
        resp = self.client.get(url)
        self.assert_contains_none(resp)


        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"severity": "GT_999999"})
        resp = self.client.get(url)
        self.assert_contains_none(resp)


    def test_severity_mod_type_filter(self):
        """
        Validates that the severity mod type filter works
        """

        # standard filtering
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"severity_modification_type": f"{SeverityMT.RECASTED}"})
        resp = self.client.get(url)
        self.assert_contains_only(resp, [self.c_critical_vuln, self.d_critical_vuln])

        # exclusion filter - Not accepted
        self.c_critical_vuln.severity_modification_type = SeverityMT.ACCEPTED
        self.d_critical_vuln.severity_modification_type = SeverityMT.ACCEPTED
        self.c_critical_vuln.save()
        self.d_critical_vuln.save()
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"severity_modification_type": "NA"})
        resp = self.client.get(url)
        self.assert_contains_all_except(resp, [self.c_critical_vuln, self.d_critical_vuln])

        # Non existent severity mod type filter
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"severity_modification_type": "999999"})
        resp = self.client.get(url)
        self.assert_contains_none(resp)


    def test_state_filter(self):
        """
        Validates that the severity filter works
        """

        # standard filtering
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"state": f"{State.REOPENED}"})
        resp = self.client.get(url)
        self.assert_contains_only(resp,[self.c_low_vuln, self.d_low_vuln])

        # exclusion filter
        self.c_low_vuln.state = State.FIXED
        self.d_low_vuln.state = State.FIXED
        self.c_low_vuln.save()
        self.d_low_vuln.save()
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"state": "NF"})
        resp = self.client.get(url)
        self.assert_contains_all_except(resp, [self.c_low_vuln, self.d_low_vuln])

        # Non existent state filter
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"state": "999999"})
        resp = self.client.get(url)
        self.assert_contains_none(resp)

    def test_asset_filter(self):
        """
        Tests that vulns can be accurately filtered by their asset
        """
        # singular vuln test
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"asset__id__exact": self.asset_vuln.pk})
        resp = self.client.get(url)
        self.assert_contains_only(resp, [self.a_high_vuln])

        # multi vuln test
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"asset__id__exact": self.asset_vulns.pk})
        resp = self.client.get(url)
        self.assert_contains_only(resp, [
            self.c_info_vuln,
            self.c_low_vuln,
            self.c_medium_vuln,
            self.c_high_vuln,
            self.c_critical_vuln
            ])

        # non-existent asset test
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"asset__id__exact":9999999999})
        resp = self.client.get(url)
        self.assert_contains_none(resp)

    def test_asset_type_filter(self):
        """
        Tests that vulns can be accurately filtered by their asset's type
        """
        # singular type test
        self.asset_vuln.add_tag(tag="TEST_DEVICE_TYPE_1", category="Devices")
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"asset_type": self.asset_vuln.tags.first().pk})
        resp = self.client.get(url)
        self.assert_contains_only(resp, [self.a_high_vuln])

        # not empty test
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"asset_type": "any"})
        resp = self.client.get(url)
        self.assert_contains_only(resp, [self.a_high_vuln])

        # empty test
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"asset_type": "none"})
        resp = self.client.get(url)
        self.assert_contains_all_except(resp, [self.a_high_vuln])

        # multi vuln type test
        self.asset_vulns.add_tag(tag="TEST_DEVICE_TYPE_2", category="Devices")
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"asset_type": self.asset_vulns.tags.first().pk})
        resp = self.client.get(url)
        self.assert_contains_only(resp, [
            self.c_info_vuln,
            self.c_low_vuln,
            self.c_medium_vuln,
            self.c_high_vuln,
            self.c_critical_vuln
            ])

        # non-existent asset test
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"asset_type":9999999999})
        resp = self.client.get(url)
        self.assert_contains_none(resp)

    def test_it_system_filter(self):
        """
        Tests that vulns can be accurately filtered by their assets related it system
        """
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"asset_systems": self.itsystem_2.pk})
        resp = self.client.get(url)

        # Test that only related vulnerabilities are found: Vulns for asset "asset_vulns_and_systems"
        self.assert_contains_only(resp,[
            self.d_info_vuln,
            self.d_low_vuln,
            self.d_medium_vuln,
            self.d_high_vuln,
            self.d_critical_vuln
        ])

        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"asset_systems": self.itsystem_1.pk})
        resp = self.client.get(url)

        # Test that only related vulnerabilities are found: Vulns for assets "asset_vulns_and_systems" and "asset_vuln_and_system"
        self.assert_contains_only(resp,[
            self.b_critical_vuln,
            self.d_info_vuln,
            self.d_low_vuln,
            self.d_medium_vuln,
            self.d_high_vuln,
            self.d_critical_vuln
        ])

        # non-existent it-system test
        url = reverse("service_desk_admin:assets_vulnerability_changelist", query={"asset_systems": 99999999999999})
        resp = self.client.get(url)
        self.assert_contains_none(resp)