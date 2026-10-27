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
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from assets.admin import pprint_json
from assets.models import Asset, Vulnerability


class PPrintJsonTestCase(SimpleTestCase):
    """
    pprint_json renders Tenable payloads into the admin inside a <pre> block.
    Payload values (hostnames, tags, banners, plugin output) are externally
    sourced and must be escaped, while the <pre> wrapper stays live HTML.
    """

    def test_escapes_html_in_values(self):
        payload = {
            "hostname": "</pre><script>alert(1)</script>",
            "banner": '"><img src=x onerror=alert(1)>',
        }

        result = str(pprint_json(payload))

        # Wrapper is still real HTML.
        self.assertTrue(result.startswith("<pre>"))
        self.assertTrue(result.endswith("</pre>"))
        # Payload is escaped.
        self.assertIn("&lt;/pre&gt;&lt;script&gt;alert(1)&lt;/script&gt;", result)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", result)
        self.assertNotIn("<script", result)
        self.assertNotIn("<img", result)

    def test_serialises_nested_data(self):
        result = str(pprint_json({"a": {"b": ["c"]}}))
        self.assertIn("&quot;a&quot;", result)
        self.assertIn("&quot;b&quot;", result)
        self.assertIn("&quot;c&quot;", result)

    def test_empty_values(self):
        self.assertEqual(pprint_json(None), "")
        self.assertEqual(pprint_json({}), "")
        self.assertEqual(pprint_json([]), "")


class VulnerabilitySummaryTestCase(TestCase):
    """The HTML summary must escape payload values but keep its own markup."""

    def setUp(self):
        self.asset = Asset.objects.create(
            tenable_id="TENABLE_ID_XSS",
            name='<script>alert("asset")</script>',
        )
        self.vuln = Vulnerability.objects.create(
            asset=self.asset,
            finding_id="FINDING_ID_XSS",
            plugin={"synopsis": "<script>alert(1)</script>", "solution": "<b>patch it</b>"},
            output="</b><script>alert(2)</script>",
        )

    def test_html_summary_escapes_payload_values(self):
        summary = str(self.vuln.html_summary)

        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", summary)
        self.assertIn("&lt;b&gt;patch it&lt;/b&gt;", summary)
        self.assertNotIn("<script", summary)
        self.assertNotIn("<b>patch it</b>", summary)
        # The property's own markup is still live HTML.
        self.assertIn("<h3>", summary)
        self.assertIn("<b>Plugin Output:</b>", summary)

    def test_plain_text_summary_is_not_escaped(self):
        """summary is a plain-text property and is not rendered as HTML."""
        self.assertIn("<script>alert(1)</script>", self.vuln.summary)

    def test_html_summary_preserves_linebreaks(self):
        self.vuln.plugin = {"synopsis": "line one\nline two"}
        self.assertIn("line one<br>line two", str(self.vuln.html_summary))

    def test_html_summary_handles_empty_vuln(self):
        vuln = Vulnerability.objects.create(
            asset=self.asset,
            finding_id="FINDING_ID_EMPTY",
            plugin={},
        )

        summary = str(vuln.html_summary)

        self.assertIn("<b>Plugin Output:</b>", summary)
        self.assertIn("<b>Solution:</b>", summary)


class AdminXSSRenderTestCase(TestCase):
    """
    End-to-end check that hostile payloads render as text in the admin change
    pages rather than executing. Covers the Asset "Raw Data" blocks and the
    Vulnerability summary/plugin/port/scan blocks.
    """

    def setUp(self):
        self.superuser = User.objects.create_superuser(username="adminuser", email="admin@example.com", password="pass")
        self.client.force_login(self.superuser)
        self.asset = Asset.objects.create(
            tenable_id="TENABLE_ID_ADMIN_XSS",
            name='<script>alert("asset-name")</script>',
            tenable_data={
                "hostnames": ['</pre><script>alert("hostname")</script>'],
                "tags": [{"key": "Devices", "value": '<img src=x onerror=alert("tag")>'}],
            },
        )
        self.vuln = Vulnerability.objects.create(
            asset=self.asset,
            finding_id="FINDING_ID_ADMIN_XSS",
            plugin={
                "name": "<b>plugin name</b>",
                "synopsis": '<img src=x onerror=alert("plugin")>',
                "solution": '<script>alert("solution")</script>',
                "vpr": {"drivers": {"age_of_vuln": {"lower_bound": 1, "upper_bound": 2}}},
            },
            output='</b><script>alert("output")</script>',
        )

    def test_asset_change_page_escapes_tenable_data(self):
        response = self.client.get(reverse("service_desk_admin:assets_asset_change", args=[self.asset.pk]))

        self.assertEqual(response.status_code, 200)
        # Asset name (readonly field).
        self.assertNotContains(response, '<script>alert("asset-name")</script>')
        self.assertContains(response, "&lt;script&gt;alert(&quot;asset-name&quot;)&lt;/script&gt;")
        # Raw tenable_data block.
        self.assertNotContains(response, "</pre><script>")
        self.assertContains(response, "&lt;/pre&gt;&lt;script&gt;")
        self.assertNotContains(response, '<img src=x onerror=alert("tag")>')

    def test_vulnerability_change_page_escapes_plugin_data(self):
        response = self.client.get(reverse("service_desk_admin:assets_vulnerability_change", args=[self.vuln.pk]))

        self.assertEqual(response.status_code, 200)
        # Summary markup is rendered as HTML...
        self.assertContains(response, "<b>Plugin Output:</b>")
        # ...but the payload within it is escaped.
        self.assertNotContains(response, '<img src=x onerror=alert("plugin")>')
        self.assertContains(response, "&lt;img src=x onerror=alert(&quot;plugin&quot;)&gt;")
        self.assertNotContains(response, '<script>alert("solution")</script>')
        # Raw plugin/scan JSON blocks are escaped too.
        self.assertNotContains(response, "</pre><script>")
