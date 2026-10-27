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
