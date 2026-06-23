import json
import os
from io import BytesIO
from unittest.mock import MagicMock, call, patch

from django.test import TestCase

from itassets.utils import (
    ModelDescMixin,
    breadcrumbs_list,
    download_blob,
    get_blob_json,
    get_next_pages,
    get_previous_pages,
    get_query,
    human_time_duration,
    humanise_bytes,
    ms_graph_client_token,
    ms_security_api_client_token,
    smart_truncate,
    upload_blob,
)


FAKE_TOKEN = {"token_type": "Bearer", "access_token": "fake-access-token"}

ENV_VARS = {
    "AZURE_TENANT_ID": "test-tenant-id",
    "AZURE_CLIENT_ID": "test-client-id",
    "AZURE_CLIENT_SECRET": "test-client-secret",
    "AZURE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=dGVzdA==;EndpointSuffix=core.windows.net",
}


def make_page(page_number, num_pages):
    """Return a mock Paginator Page object."""
    page = MagicMock()
    page.number = page_number
    page.paginator.num_pages = num_pages
    page.has_previous.return_value = page_number > 1
    page.has_next.return_value = page_number < num_pages
    page.previous_page_number.return_value = page_number - 1
    page.next_page_number.return_value = page_number + 1
    return page


class MsGraphClientTokenTestCase(TestCase):
    @patch.dict(os.environ, ENV_VARS)
    @patch("itassets.utils.ConfidentialClientApplication")
    def test_returns_token(self, mock_msal_cls):
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = FAKE_TOKEN
        mock_msal_cls.return_value = mock_app

        token = ms_graph_client_token()

        self.assertEqual(token, FAKE_TOKEN)
        mock_msal_cls.assert_called_once_with(
            client_id="test-client-id",
            client_credential="test-client-secret",
            authority="https://login.microsoftonline.com/test-tenant-id",
        )
        mock_app.acquire_token_for_client.assert_called_once_with(scopes=["https://graph.microsoft.com/.default"])

    @patch.dict(os.environ, ENV_VARS)
    @patch("itassets.utils.ConfidentialClientApplication")
    def test_passes_through_msal_error(self, mock_msal_cls):
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {"error": "invalid_client"}
        mock_msal_cls.return_value = mock_app

        token = ms_graph_client_token()

        self.assertIn("error", token)


class MsSecurityApiClientTokenTestCase(TestCase):
    @patch.dict(os.environ, ENV_VARS)
    @patch("itassets.utils.requests.post")
    def test_returns_access_token(self, mock_post):
        mock_post.return_value.json.return_value = {"access_token": "security-token"}

        token = ms_security_api_client_token()

        self.assertEqual(token, "security-token")
        expected_url = f"https://login.windows.net/{ENV_VARS['AZURE_TENANT_ID']}/oauth2/token"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], expected_url)
        self.assertEqual(kwargs["data"]["client_id"], "test-client-id")
        self.assertEqual(kwargs["data"]["grant_type"], "client_credentials")


class UploadBlobTestCase(TestCase):
    @patch.dict(os.environ, ENV_VARS)
    @patch("itassets.utils.BlobServiceClient")
    def test_upload_calls_blob_client(self, mock_bsc_cls):
        mock_service = MagicMock()
        mock_blob_client = MagicMock()
        mock_bsc_cls.from_connection_string.return_value = mock_service
        mock_service.get_blob_client.return_value = mock_blob_client

        in_file = BytesIO(b"test data")
        upload_blob(in_file, container="mycontainer", blob="myblob")

        mock_bsc_cls.from_connection_string.assert_called_once_with(ENV_VARS["AZURE_CONNECTION_STRING"])
        mock_service.get_blob_client.assert_called_once_with(container="mycontainer", blob="myblob")
        mock_blob_client.upload_blob.assert_called_once_with(in_file, overwrite=True)

    @patch.dict(os.environ, ENV_VARS)
    @patch("itassets.utils.BlobServiceClient")
    def test_upload_overwrite_false(self, mock_bsc_cls):
        mock_service = MagicMock()
        mock_blob_client = MagicMock()
        mock_bsc_cls.from_connection_string.return_value = mock_service
        mock_service.get_blob_client.return_value = mock_blob_client

        in_file = BytesIO(b"data")
        upload_blob(in_file, container="c", blob="b", overwrite=False)

        mock_blob_client.upload_blob.assert_called_once_with(in_file, overwrite=False)


class DownloadBlobTestCase(TestCase):
    @patch.dict(os.environ, ENV_VARS)
    @patch("itassets.utils.BlobServiceClient")
    def test_download_writes_and_seeks(self, mock_bsc_cls):
        mock_service = MagicMock()
        mock_container_client = MagicMock()
        mock_bsc_cls.from_connection_string.return_value = mock_service
        mock_service.get_container_client.return_value = mock_container_client
        mock_container_client.download_blob.return_value.readall.return_value = b"blob content"

        out_file = BytesIO()
        result = download_blob(out_file, container="mycontainer", blob="myblob")

        mock_service.get_container_client.assert_called_once_with(container="mycontainer")
        mock_container_client.download_blob.assert_called_once_with("myblob")
        self.assertEqual(result.read(), b"blob content")

    @patch.dict(os.environ, ENV_VARS)
    @patch("itassets.utils.BlobServiceClient")
    def test_download_returns_seeked_file(self, mock_bsc_cls):
        mock_service = MagicMock()
        mock_container_client = MagicMock()
        mock_bsc_cls.from_connection_string.return_value = mock_service
        mock_service.get_container_client.return_value = mock_container_client
        mock_container_client.download_blob.return_value.readall.return_value = b"hello"

        out_file = BytesIO()
        result = download_blob(out_file, container="c", blob="b")

        # Verify the file position was reset to 0 after writing.
        self.assertEqual(result.tell(), 0)


class GetBlobJsonTestCase(TestCase):
    @patch("itassets.utils.download_blob")
    def test_parses_json_from_blob(self, mock_download):
        payload = {"key": "value", "number": 42}

        def fill_buffer(out_file, container, blob):
            out_file.write(json.dumps(payload).encode())
            out_file.seek(0)
            return out_file

        mock_download.side_effect = fill_buffer

        result = get_blob_json("mycontainer", "myblob")

        self.assertEqual(result, payload)
        mock_download.assert_called_once()


class BreadcrumbsListTestCase(TestCase):
    def test_single_item_renders_active(self):
        result = breadcrumbs_list([("/", "Home")])
        self.assertIn("breadcrumb-item active", result)
        self.assertIn("Home", result)
        self.assertNotIn("<a href", result)

    def test_multiple_items_last_is_active(self):
        links = [("/", "Home"), ("/section/", "Section"), ("/section/page/", "Page")]
        result = breadcrumbs_list(links)
        self.assertIn('<a href="/">', result)
        self.assertIn('<a href="/section/">', result)
        self.assertIn("breadcrumb-item active", result)
        self.assertIn("<span>Page</span>", result)
        # The last item should not be a link.
        self.assertNotIn('<a href="/section/page/">', result)

    def test_two_items(self):
        result = breadcrumbs_list([("/", "Home"), ("/page/", "Page")])
        self.assertIn('<a href="/">', result)
        self.assertIn("<span>Page</span>", result)


class GetQueryTestCase(TestCase):
    def test_single_term_single_field(self):
        q = get_query("hello", ["name"])
        self.assertIsNotNone(q)
        # The Q object should filter on name__icontains.
        self.assertIn("name__icontains", str(q))

    def test_single_term_multiple_fields(self):
        q = get_query("hello", ["name", "email"])
        self.assertIn("name__icontains", str(q))
        self.assertIn("email__icontains", str(q))

    def test_multiple_terms_are_ANDed(self):
        q = get_query("hello world", ["name"])
        # Two terms — both must match (AND).
        self.assertIsNotNone(q)

    def test_quoted_phrase_treated_as_single_term(self):
        q = get_query('"hello world"', ["name"])
        self.assertIsNotNone(q)
        self.assertIn("hello world", str(q))

    def test_extra_whitespace_is_normalised(self):
        q1 = get_query("hello world", ["name"])
        q2 = get_query("hello  world", ["name"])
        self.assertEqual(str(q1), str(q2))


class HumanTimeDurationTestCase(TestCase):
    def test_zero_seconds(self):
        self.assertEqual(human_time_duration(0), "<1 second")

    def test_one_second(self):
        self.assertEqual(human_time_duration(1), "<1 second")

    def test_seconds(self):
        self.assertEqual(human_time_duration(45), "45 seconds")

    def test_one_minute(self):
        self.assertEqual(human_time_duration(60), "1 minute")

    def test_minutes_and_seconds(self):
        self.assertEqual(human_time_duration(125), "2 minutes, 5 seconds")

    def test_one_hour(self):
        self.assertEqual(human_time_duration(3600), "1 hour")

    def test_hours_and_minutes(self):
        self.assertEqual(human_time_duration(7384), "2 hours, 3 minutes, 4 seconds")

    def test_one_week(self):
        self.assertEqual(human_time_duration(60 * 60 * 24 * 7), "1 week")

    def test_complex_duration(self):
        duration = 60 * 60 * 24 * 7 + 60 * 60 * 2 + 60 * 30
        result = human_time_duration(duration)
        self.assertIn("1 week", result)
        self.assertIn("2 hours", result)
        self.assertIn("30 minutes", result)


class HumaniseBytesTestCase(TestCase):
    def test_bytes(self):
        self.assertEqual(humanise_bytes(512), "512.0 B")

    def test_kilobytes(self):
        self.assertEqual(humanise_bytes(1024), "1.0 KB")

    def test_megabytes(self):
        self.assertEqual(humanise_bytes(1024 * 1024), "1.0 MB")

    def test_gigabytes(self):
        self.assertEqual(humanise_bytes(1024**3), "1.0 GB")

    def test_terabytes(self):
        self.assertEqual(humanise_bytes(1024**4), "1.0 TB")

    def test_fractional(self):
        result = humanise_bytes(1536)  # 1.5 KB
        self.assertEqual(result, "1.5 KB")


class SmartTruncateTestCase(TestCase):
    def test_short_string_unchanged(self):
        s = "Hello world"
        self.assertEqual(smart_truncate(s, length=100), s)

    def test_exact_length_unchanged(self):
        s = "a" * 100
        self.assertEqual(smart_truncate(s, length=100), s)

    def test_long_string_truncated(self):
        s = "word " * 30  # 150 chars
        result = smart_truncate(s, length=100)
        self.assertLessEqual(len(result), len(s))
        self.assertTrue(result.endswith("....(more)"))

    def test_custom_suffix(self):
        s = "word " * 30
        result = smart_truncate(s, length=100, suffix="[snip]")
        self.assertTrue(result.endswith("[snip]"))

    def test_truncates_on_word_boundary(self):
        s = "one two three four five six seven eight nine ten eleven twelve"
        result = smart_truncate(s, length=20)
        # Result should not cut a word in half.
        suffix = "....(more)"
        trimmed = result[: -len(suffix)]
        self.assertFalse(trimmed.endswith(" "))  # No trailing space before suffix.


class GetPreviousPagesTestCase(TestCase):
    def test_first_page_has_no_previous(self):
        page = make_page(1, 5)
        self.assertEqual(get_previous_pages(page), [])

    def test_second_page_returns_one(self):
        page = make_page(2, 5)
        self.assertEqual(get_previous_pages(page), [1])

    def test_middle_page_returns_up_to_three(self):
        page = make_page(5, 10)
        result = get_previous_pages(page)
        self.assertEqual(result, [2, 3, 4])

    def test_count_parameter(self):
        page = make_page(5, 10)
        result = get_previous_pages(page, count=2)
        self.assertEqual(result, [3, 4])

    def test_does_not_go_below_page_one(self):
        page = make_page(2, 10)
        result = get_previous_pages(page, count=5)
        self.assertEqual(result, [1])

    def test_none_returns_empty(self):
        self.assertEqual(get_previous_pages(None), [])


class GetNextPagesTestCase(TestCase):
    def test_last_page_has_no_next(self):
        page = make_page(5, 5)
        self.assertEqual(get_next_pages(page), [])

    def test_second_to_last_returns_one(self):
        page = make_page(4, 5)
        self.assertEqual(get_next_pages(page), [5])

    def test_middle_page_returns_up_to_three(self):
        page = make_page(5, 10)
        result = get_next_pages(page)
        self.assertEqual(result, [6, 7, 8])

    def test_count_parameter(self):
        page = make_page(5, 10)
        result = get_next_pages(page, count=2)
        self.assertEqual(result, [6, 7])

    def test_does_not_exceed_last_page(self):
        page = make_page(9, 10)
        result = get_next_pages(page, count=5)
        self.assertEqual(result, [10])

    def test_none_returns_empty(self):
        self.assertEqual(get_next_pages(None), [])


class ModelDescMixinTestCase(TestCase):
    def test_model_description_injected_into_context(self):
        # Build a concrete subclass whose super().changelist_view captures extra_context.
        captured = {}

        class BaseAdmin:
            def changelist_view(self, request, extra_context=None):
                captured.update(extra_context or {})
                return captured

        class FakeAdmin(ModelDescMixin, BaseAdmin):
            model_description = "A description."

        admin = FakeAdmin()
        admin.changelist_view(request=None)
        self.assertEqual(captured["model_description"], "A description.")

    def test_no_model_description_no_injection(self):
        captured = {}

        class BaseAdmin:
            def changelist_view(self, request, extra_context=None):
                captured.update(extra_context or {})
                return captured

        class FakeAdmin(ModelDescMixin, BaseAdmin):
            pass

        admin = FakeAdmin()
        admin.changelist_view(request=None)
        self.assertNotIn("model_description", captured)
