from requests.exceptions import HTTPError
import logging

from django.test import TestCase, override_settings
from assets.tenable_requests import tenable_export_assets, TenableExporter
from unittest.mock import patch


@override_settings(TENABLE_ACCESS_KEY="test-access-key", TENABLE_SECRET_KEY="test-secret-key")
class TenableRequestsTestCase(TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    def test_api_key_header(self):
        exporter = TenableExporter(base_url="https://cloud.tenable.com/assets/export", export_payload={})
        self.assertEqual(exporter.export_headers["X-ApiKeys"], "accessKey=test-access-key;secretKey=test-secret-key")
        self.assertEqual(exporter.check_headers["X-ApiKeys"], "accessKey=test-access-key;secretKey=test-secret-key")

    @override_settings(TENABLE_EXPORT_STATUS_CHECK_LIMIT=3)
    @patch("assets.tenable_requests.time.sleep")
    @patch("assets.tenable_requests.TenableExporter.download_export_chunk")
    @patch("assets.tenable_requests.TenableExporter.check_status")
    @patch("assets.tenable_requests.TenableExporter.initiate_export")
    def test_tenable_export(self, mock_export, mock_status, mock_chunk, mock_sleep):
        """
        Tests all reasonable paths of the tenable_export function.
        Uses tenable_export_assets() as the test entry point.
        tenable_export_vulns works identically, just with different payloads and urls, which are irrelevant for path tests.
        """
        # Paths
        # 1. Initiate failure / exception
        # 2. Initiate -> check-wait failure / exception
        # 3. Initiate -> check-wait -> download failure(s)
        # 4. Initiate -> check-wait -> download
        # Failures can be exception or an empty/ None return

        # Path 1 - exception & None failure
        mock_export.side_effect = HTTPError
        assets = tenable_export_assets()
        mock_export.assert_called_once()
        mock_status.assert_not_called()
        mock_chunk.assert_not_called()
        self.assertEqual(assets, [])

        # path 2
        # 2.1 Immediate http error
        mock_export.reset_mock()
        mock_status.reset_mock()
        mock_export.side_effect = None
        mock_export.return_value = {"export_uuid": "random_uuid"}
        mock_status.side_effect = HTTPError
        assets = tenable_export_assets()
        mock_export.assert_called_once()
        mock_status.assert_called_once()
        mock_chunk.assert_not_called()
        self.assertEqual(assets, [])

        # 2.2 failed status_code, then successful with error message
        mock_export.reset_mock()
        mock_status.reset_mock()
        mock_status.side_effect = None
        mock_export.return_value = {"export_uuid": "random_uuid"}
        mock_status.side_effect = [{"status": "QUEUED"}, {"status": "ERROR"}]
        assets = tenable_export_assets()
        mock_export.assert_called_once()
        self.assertEqual(mock_status.call_count, 2)
        mock_chunk.assert_not_called()
        self.assertEqual(assets, [])

        # 2.3 failures run out the loop
        mock_export.reset_mock()
        mock_status.reset_mock()
        mock_export.side_effect = None
        mock_export.return_value = {"export_uuid": "random_uuid"}
        mock_status.side_effect = [{"status": "QUEUED"}, {"status": "QUEUED"}, {"status": "QUEUED"}]
        assets = tenable_export_assets()
        mock_export.assert_called_once()
        self.assertEqual(mock_status.call_count, 3)
        mock_chunk.assert_not_called()
        self.assertEqual(assets, [])

        # path 3
        # 3.1 Immediate http error
        mock_export.reset_mock()
        mock_status.reset_mock()
        mock_status.side_effect = None
        mock_export.return_value = {"export_uuid": "random_uuid"}
        mock_status.return_value = {"status": "FINISHED", "chunks_available": [1, 2, 3]}
        mock_chunk.side_effect = HTTPError
        assets = tenable_export_assets()
        self.assertEqual(assets, [])
        mock_export.assert_called_once()
        mock_status.assert_called_once()
        mock_chunk.assert_called_once()

        # 3.1 Complete download
        mock_export.reset_mock()
        mock_status.reset_mock()
        mock_chunk.reset_mock()
        mock_chunk.side_effect = None
        mock_status.side_effect = None
        mock_export.return_value = {"export_uuid": "random_uuid"}
        mock_status.return_value = {"status": "FINISHED", "chunks_available": [1, 2, 3]}
        mock_chunk.side_effect = ["a", "b", "c"]
        assets = tenable_export_assets()
        mock_export.assert_called_once()
        mock_status.assert_called_once()
        self.assertEqual(mock_chunk.call_count, 3)
        self.assertEqual(assets, ["a", "b", "c"])
