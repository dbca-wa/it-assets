from django.test import TestCase, override_settings
from django.utils.timezone import localtime as now

from datetime import timedelta
from unittest.mock import patch

from assets.management.commands import sync_to_tenable
from assets.tests.test_model import RandomVulnGenerator as Vgen, RandomAssetGenerator as Agen
from assets.models import Vulnerability

class ExportsTestCase(TestCase):
    def setUp(self):
        self.cmd = sync_to_tenable.Command()

    def test_passes_filter(self):
        """
        Tests that the passes_filter() method accurately filters out undesirable assets.
        Asset must contain the device tag, or be a web app.
        If the asset isn't a web app, the Asset must not contain a user device tag, new device tag, or an edge firewall tag.
        """

        # asset contains only a filtered out tag - Invalid
        asset = {"types":["host"], "tags":[
            {"key":"Devices", "value":"User Device"}
            ]}

        self.assertFalse(self.cmd.passes_filter(asset))

        # asset contains a filtered out tag and a passing tag - Invalid
        asset = {"types":["host"], "tags":[
            {"key":"Devices", "value":"User Device"},
            {"key":"Devices", "value":"RandomVal"}
            ]}
        self.assertFalse(self.cmd.passes_filter(asset))


        # asset contains no device tags - Invalid
        asset = {"types":["host"], "tags":[
            {"key":"rand1", "value":"randomValue"},
            {"key":"rand2", "value":"RandomVal"}
            ]}
        
        self.assertFalse(self.cmd.passes_filter(asset))

        # asset contains not tags - invalid
        asset = {"types":["host"]}
        self.assertFalse(self.cmd.passes_filter(asset))

        # asset contains only valid tags - Valid
        asset = {"types":["host"], "tags":[
            {"key":"Devices", "value":"Server"},
            {"key":"RandomTag", "value":"RandomVal"}
            ]}
        self.assertTrue(self.cmd.passes_filter(asset))

        # asset contains no tags and is a web app - Valid
        asset = {"types":["webapp"]}
        self.assertTrue(self.cmd.passes_filter(asset))

        # asset contains valid tags and is a web app - Valid
        asset = {"types":["webapp"], "tags":[
            {"key":"Devices", "value":"Server"},
            {"key":"RandomTag", "value":"RandomVal"}
            ]}
        self.assertTrue(self.cmd.passes_filter(asset))

        # asset contains invalid tags and is a web app - Valid
        asset = {"types":["webapp"], "tags":[
            {"key":"Devices", "value":"User Device"}
            ]}
        self.assertTrue(self.cmd.passes_filter(asset))

    @patch("assets.management.commands.sync_to_tenable.tenable_export_vulns")
    @patch("assets.management.commands.sync_to_tenable.tenable_export_web_app_vulns")
    def test_get_vulns_per_asset(self, mock_web_vulns, mock_asset_vulns):
        """
        Tests that the get_vulns_per_asset() method accurately returns a dict of vuln lists per asset.
        """
        asset1, asset2 = Agen().generate(2)
        mock_asset_vulns.return_value = []
        mock_web_vulns.return_value = []

        # Tests
        # Multiple assigned to diff assets
        # Multiple assigned to the same assets
        # Data comes from web app & asset exports
        vulns1 = [
            {"finding_id":"1","asset":{"uuid":asset1.tenable_id}},
            {"finding_id":"2","asset":{"uuid":asset2.tenable_id}}
            ]
        vulns2 = [
            {"finding_id":"3","asset":{"uuid":asset1.tenable_id}},
            {"finding_id":"4","asset":{"uuid":asset2.tenable_id}}
            ]
        mock_asset_vulns.return_value = vulns1
        mock_web_vulns.return_value = vulns2

        # Get vulns per asset
        results = self.cmd.get_vulns_per_asset()

        # Assert Vulns accurately returned and assigned to the right asset
        self.assertEqual(len(results),2)
        self.assertEqual(len(results[asset1.tenable_id]),2)
        self.assertEqual(len(results[asset2.tenable_id]),2)
        self.assertIn({"finding_id":"1","asset":{"uuid":asset1.tenable_id}},results[asset1.tenable_id])
        self.assertIn({"finding_id":"3","asset":{"uuid":asset1.tenable_id}},results[asset1.tenable_id])
        self.assertIn({"finding_id":"2","asset":{"uuid":asset2.tenable_id}},results[asset2.tenable_id])
        self.assertIn({"finding_id":"4","asset":{"uuid":asset2.tenable_id}},results[asset2.tenable_id])

        # No vulns retrieved
        mock_asset_vulns.return_value = {}
        mock_web_vulns.return_value = {}        
        results = self.cmd.get_vulns_per_asset()
        self.assertEqual(results,{})

        # Exception raised during retrieval - None returned
        mock_asset_vulns.side_effect = Exception
        results = self.cmd.get_vulns_per_asset()
        self.assertEqual(results,{})


    @override_settings(VULN_LAST_SEEN_LIMIT=30)
    def test_prune_aged_out_vulns(self):
        """
        Tests that vulnerabilities are accurately pruned as per their last_found date and the vuln_last_seen_limit
        """

        # Generate vulns and assets        
        asset, = Agen().generate(1)
        vuln_current,vuln_close,vuln_expired = Vgen().generate(asset, 3)
        current_id = vuln_current.finding_id
        close_id = vuln_close.finding_id
        expired_id = vuln_expired.finding_id

        # Set last_found to before limit, on limit, and after limit
        vuln_current.last_found = now() - timedelta(days=29)
        vuln_current.save()
        vuln_close.last_found = now() - timedelta(days=30)
        vuln_close.save()
        vuln_expired.last_found = now() - timedelta(days=60)
        vuln_expired.save()

        # prune aged out vulns
        self.cmd.prune_aged_out_vulns()

        # Verify accurately pruned
        self.assertTrue(Vulnerability.objects.filter(finding_id = current_id).exists())
        self.assertFalse(Vulnerability.objects.filter(finding_id = close_id).exists())
        self.assertFalse(Vulnerability.objects.filter(finding_id = expired_id).exists())
        self.assertEqual(len(Vulnerability.objects.all()),1)