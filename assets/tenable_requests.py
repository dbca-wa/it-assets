import logging
import requests
import json
import os
import time
from datetime import timedelta

from django.utils.timezone import localtime as now
from django.conf import settings
from assets.utils import get_with_retry, post_with_retry

LOGGER = logging.getLogger("assets")

def get_tenable_key_string() -> str:
    """
    Returns an auth key string used for tenable api requests
    """
    access_key = settings.TENABLE_ACCESS_KEY
    secret_key = settings.TENABLE_SECRET_KEY
    if not access_key or not secret_key:
        raise Exception("TENABLE_ACCESS_KEY and TENABLE_SECRET_KEY must both be set.")
    return f"accessKey={access_key};secretKey={secret_key}"


class TenableExporter:
    """
    Provides a class for handling tenable export web requests.
    """

    def __init__(self, base_url: str, export_payload: dict, export_headers: dict | None = None, check_headers: dict | None = None, download_headers: dict | None = None, alt_export_url: str | None = None) -> None:
        self.base_url = base_url  # Mandatory
        self.export_payload = export_payload  # Mandatory
        self.alt_export_url = alt_export_url  # Optional
        self.export_headers = self.headers_with_api_key(export_headers if export_headers else {"accept": "application/json", "content-type": "application/json"})
        self.check_headers = self.headers_with_api_key(check_headers if check_headers else {"accept": "application/json"})
        self.download_headers = self.headers_with_api_key(download_headers if download_headers else {"accept": "application/json"})

    def headers_with_api_key(self, headers) -> dict:
        return {**headers, "X-ApiKeys": get_tenable_key_string()}

    def initiate_export(self, retries: int = 0) -> dict | None:
        """
        Queries the Tenable Nessus endpoint to initate an export of all recorded assets, and returns the export uuid.
        If an automatic_retries number is specified, any 429 errors will automatically retry that many times.
        """
        url = self.alt_export_url if self.alt_export_url else self.base_url
        response = post_with_retry(url=url, headers=self.export_headers, payload=self.export_payload, retries=3)

        return json.loads(response.content)

    def check_status(self, export_uuid: str, retries: int = 3) -> dict | None:
        url = f"{self.base_url}/{export_uuid}/status"
        response = get_with_retry(url=url, headers=self.check_headers, retries=retries)

        return json.loads(response.content)

    def download_export_chunk(self, export_uuid: str, chunk_id: int, retries: int = 3) -> list | None:
        """
        Queries the Tenable Nessus endpoint to retrieve a chunk of the asset export.
        Returns a list of dicts representing the assets.
        """
        url = f"{self.base_url}/{export_uuid}/chunks/{chunk_id}"

        response = get_with_retry(url=url, headers=self.download_headers, retries=retries)

        # Allows for json and octet formatting methods.
        if "json" in self.download_headers["accept"]:
            return json.loads(response.content)
        elif "octet" in self.download_headers["accept"]:
            return json.loads(response.text)


def tenable_export_assets() -> list:
    """
    Initiates a Tenable asset export and downloads the result once the export is complete.
    """
    return tenable_export(
        # Pass through a TenableExporter populated for the asset endpoints
        TenableExporter(
            base_url="https://cloud.tenable.com/assets/export",
            alt_export_url="https://cloud.tenable.com/assets/v2/export",
            export_payload={
                "include_resource_tags": True,
                "include_open_ports": False,
                "chunk_size": 1000,
                "filters": {"types": ["host", "webapp"]}, # includes web apps
            },
        )
    )


def tenable_export_vulns() -> list:
    """
    Initiates a Tenable vulnerability export and downloads the result once the export is complete.
    """
    return tenable_export(
        # Pass through a TenableExporter populated for the vulnerability endpoints
        TenableExporter(
            base_url="https://cloud.tenable.com/vulns/export",
            export_payload={
                "include_unlicensed": True,
                "num_assets": 1000,
                "include_software_vulns": False,
                "filters": {
                    "last_seen": int((now() - timedelta(days=7)).timestamp()),  # seen within 1 week
                    "severity": ["low", "medium", "high", "critical"],  # filters out info level vulns
                },
            },
            download_headers={"accept": "application/octet-stream", "X-ApiKeys": get_tenable_key_string()},
        )
    )

def tenable_export_web_app_vulns() -> list:
    """
    Initiates a Tenable web app vulnerability export and downloads the result once the export is complete.
    """
    return tenable_export(
        # Pass through a TenableExporter populated for the vulnerability endpoints
        TenableExporter(
            base_url="https://cloud.tenable.com/was/v1/export/vulns",
            export_payload={
                "include_unlicensed": True,
                "num_assets": 1000,
                "filters": {
                    "last_found": int((now() - timedelta(days=7)).timestamp()),  # seen within 1 week
                    "severity": ["low", "medium", "high", "critical"],  # filters out info level vulns
                },
            },
            download_headers={"accept": "application/octet-stream", "X-ApiKeys": get_tenable_key_string()},
        )
    )


def tenable_export(exporter: TenableExporter) -> list:
    """
    Queries the tenable API using a TenableExporter, returning the results of the export as a list of dicts.
    """
    exports = []
    export_uuid = None
    chunks_available = []

    # Initiate tenable export
    try:
        response = exporter.initiate_export(retries=3)
        if response:
            export_uuid = response.get("export_uuid")
        LOGGER.info("Initiated Tenable data export")
    except (requests.exceptions.HTTPError, requests.exceptions.RequestException) as exc:
        export_uuid = None
        LOGGER.warning("Failed to initiate Tenable data export", exc_info=exc)

    # Checks export status until the export is completed, failed, or the check limit as run out.
    if export_uuid:
        LOGGER.info("Waiting for export to complete...")
        limit = settings.TENABLE_EXPORT_STATUS_CHECK_LIMIT
        for i in range(limit):
            try:
                # Attempt status check
                response = exporter.check_status(export_uuid=export_uuid, retries=3)
                # Retrieve status
                status = response.get("status") if response else None
                # Sleeps if export is still in process, else reports the result and exits the loop
                match status:
                    case "QUEUED" | "PROCESSING":  # Export still in process - Wait for <TENABLE_EXPORT_CHECK_DELAY> seconds
                        LOGGER.info(
                            f"Attempt [{i}/{limit}]: Export status [{status}] - Sleeping for {settings.TENABLE_EXPORT_CHECK_DELAY} seconds..."
                        )
                        time.sleep(settings.TENABLE_EXPORT_CHECK_DELAY)
                    case "FINISHED":  # Export finished
                        chunks_available = response.get("chunks_available", [])
                        LOGGER.info(
                            f"Attempt [{i}/{limit}]: Export status [{status}] - {len(chunks_available)} chunks available for download"
                        )
                        break
                    case "ERROR":  # Tenable ran into an error while exporting
                        LOGGER.warning(
                            f"Attempt [{i}/{limit}]: Export status [{status}] - ERROR: {response.get('reason', 'Unknown Error, response did not contain error message')}"
                        )
                        break
                    case "CANCELLED":  # Export was cancelled by admin - Likely rare to happen, but worth accounting for
                        LOGGER.warning(f"Attempt [{i}/{limit}]: Export status [{status}] - request cancelled by an administrator")
                        break
                    case _:  # initiate asset export returned empty
                        LOGGER.warning(f"Attempt [{i}/{limit}]: Failed to export Tenable data - Empty return value from status check")
                        break
            except requests.exceptions.HTTPError as exc:
                LOGGER.warning(f"Attempt [{i}/{limit}]: Failed to export Tenable data - exception raised during status check", exc_info=exc)
                break

    # Downloads export chunks
    chunks_downloaded = 0
    if len(chunks_available) > 0:
        LOGGER.info(f"Downloading {len(chunks_available)} chunks...")
        for chunk_id in chunks_available:
            try:
                chunk = exporter.download_export_chunk(export_uuid=export_uuid, chunk_id=int(chunk_id), retries=3)
                if chunk:
                    exports.extend(chunk)
                    chunks_downloaded += 1
                    LOGGER.info(f"Downloaded chunk {chunk_id} - current export size {len(exports)}")
                else:
                    LOGGER.info(f"Failed to download chunk {chunk_id} - no data returned")
            except requests.exceptions.HTTPError as exc:
                LOGGER.warning(f"Failed to download chunk {chunk_id} - exception raised during status check", exc_info=exc)
                break

        LOGGER.info(
            f"""Download complete: Chunks downloaded - {chunks_downloaded}/{len(chunks_available)} | items downloaded - {len(exports)}"""
        )

    return exports
