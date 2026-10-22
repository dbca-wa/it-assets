from django.test import TestCase

from assets.utils import alias_get_or_create, get_with_retry, post_with_retry
from assets.models import Asset
from assets.tests.test_model import RandomAssetGenerator as Gen

from unittest.mock import MagicMock, patch
import json


class UtilsTestCase(TestCase):
    def test_alias_get_or_create(self):
        """
        Tests that alias_get_or_create works as intended
        """
        asset1, asset2 = Gen().generate(2)
        asset1.aliases = ["name1", "name2", "name3"]
        asset2.aliases = ["test1", "test1.name.domain", "name3"]
        asset1.save()
        asset2.save()

        # Test no new assets are created for a device with an existing alias
        self.assertEqual(len(Asset.objects.all()), 2)
        new_asset, created = alias_get_or_create(aliases=["name1", "blah blah", "woah"])
        self.assertEqual(created, False)
        self.assertEqual(new_asset.pk, asset1.pk)
        self.assertEqual(len(Asset.objects.all()), 2)

        # Tests that a new asset is created for a device without an existing alias
        new_asset, created = alias_get_or_create(aliases=["name", "new", "new2"])
        self.assertEqual(created, True)
        self.assertNotEqual(new_asset.pk, asset1.pk)
        self.assertNotEqual(new_asset.pk, asset2.pk)
        self.assertEqual(len(Asset.objects.all()), 3)

        # Tests that the first asset found is returned when other aliases match others
        new_asset, created = alias_get_or_create(aliases=["name1", "name", "tester3"])
        self.assertEqual(created, False)
        self.assertEqual(new_asset.pk, asset1.pk)
        self.assertEqual(len(Asset.objects.all()), 3)

        # Tests that when multiple assets share the same alias, only the first found is returned
        new_asset, created = alias_get_or_create(aliases=["name3"])
        self.assertEqual(created, False)
        self.assertTrue(new_asset.pk == asset1.pk or new_asset.pk == asset2.pk)
        self.assertEqual(len(Asset.objects.all()), 3)

    @patch("assets.utils.time.sleep")
    @patch("assets.utils.requests.post")
    @patch("assets.utils.requests.get")
    def test_get_and_post(self, mock_get, mock_post, mock_sleep):
        """ "
        Tests the post and get web request
        """

        # standard test
        mock_get.return_value = mock_response(data=json.dumps(True))
        resp = get_with_retry(url="", headers={})
        self.assertEqual(resp.content, "true")
        mock_sleep.assert_not_called()
        self.assertEqual(mock_get.call_count, 1)
        resp.raise_for_status.assert_called_once()

        # 429 failure test - 1 retry
        mock_get.side_effect = [
            mock_response(data=json.dumps(False), status_code=429),
            mock_response(data=json.dumps(True)),
        ]
        resp = get_with_retry(url="", headers={})
        self.assertEqual(resp.content, "true")
        mock_sleep.assert_called_once()
        self.assertEqual(mock_sleep.call_count, 1)
        self.assertEqual(mock_get.call_count, 3)

        # 429 failure test - 2 retries
        mock_get.side_effect = [
            mock_response(data=json.dumps(False), status_code=429),
            mock_response(data=json.dumps(False), status_code=429),
            mock_response(data=json.dumps(True)),
        ]
        resp = get_with_retry(url="", headers={}, retries=3)
        self.assertEqual(resp.content, "true")
        self.assertEqual(mock_sleep.call_count, 3)
        self.assertEqual(mock_get.call_count, 6)

        # 429 escape early test
        mock_get.side_effect = [
            mock_response(data=json.dumps(False), status_code=429),
            mock_response(data=json.dumps(False), status_code=429),
            mock_response(data=json.dumps(True)),
        ]
        resp = get_with_retry(url="", headers={}, retries=1)
        self.assertEqual(resp.content, "false")
        self.assertEqual(mock_sleep.call_count, 4)
        self.assertEqual(mock_get.call_count, 8)

        # standard post test
        mock_post.return_value = mock_response(data=json.dumps(True))
        resp = post_with_retry(url="", headers={}, payload={"test": "test"})
        self.assertEqual(resp.content, "true")
        self.assertEqual(mock_sleep.call_count, 4)
        mock_post.assert_called_once()
        mock_post.assert_called_with("", json=json.dumps({"test": "test"}), headers={})
        resp.raise_for_status.assert_called_once()


def mock_response(data, status_code=200, headers=None) -> MagicMock:
    """Return a mock requests.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = data
    if headers:
        resp.headers = headers
    resp.raise_for_status.return_value = None
    return resp
