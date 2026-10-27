import json
import os
import re
import time
from collections.abc import Callable
from urllib.parse import urlparse

import requests
from django.utils.timezone import localtime as now
from github import Github
from github.Auth import Token

from assets.models import Asset, Repository, RepositoryAdvisory


def alias_get_or_create(aliases: list) -> tuple[Asset, bool]:
    """
    Get or Create an asset based on the list of aliases for that asset.
    Returns a tuple of (Asset <Asset>, Created <bool>).
    If multiple assets are found, only return the first
    """
    for name in aliases:
        if Asset.objects.filter(aliases__contains=name).exists():
            return Asset.objects.filter(aliases__contains=name).first(), False
    return Asset.objects.create(name=aliases[0], aliases=aliases, last_seen=now()), True


def get_with_retry(url: str, headers: dict, retries: int = 3) -> requests.Response:
    """
    Makes a GET web request, retrying 429 errors after sleeping and raising other errors.
    Retries 429 errors 1 time by default.
    """
    return __wr_with_retry(lambda: requests.get(url, headers=headers), retries)


def post_with_retry(url: str, headers: dict, payload: dict, retries: int = 3) -> requests.Response:
    """
    Makes a Post web request, retrying 429 errors after sleeping and raising other errors.
    Retries 429 errors 1 time by default.
    """
    json_payload = json.dumps(payload)
    return __wr_with_retry(lambda: requests.post(url, json=json_payload, headers=headers), retries)


def __wr_with_retry(request: Callable, retries: int) -> requests.Response:
    """
    Sends web requests using an inputted lambda, then handles any rate limitting issues.
    """
    response = request()

    # Automatically sleep and retry any rate 429 rate limiting responses
    if response.status_code == 429 and retries > 0:
        attempts = 0
        while response.status_code == 429 and retries > attempts:
            attempts += 1
            time.sleep(int(response.headers.get("retry-after")))
            response = request()

    response.raise_for_status()

    return response


def get_github_organisation():
    github_token = os.getenv("GITHUB_TOKEN", None)
    if not github_token:
        return
    token = Token(github_token)
    github = Github(auth=token)
    github_organisation = settings.GITHUB_ORGANISATION
    return github.get_organization(github_organisation)


def _parse_github_repo_slug(repo_url: str) -> str:
    """Normalise a GitHub repository URL into the owner/repo format."""
    cleaned = repo_url.strip().rstrip("/")
    if not cleaned:
        raise ValueError("Repository URL is empty")

    if cleaned.startswith("git@github.com:"):
        cleaned = cleaned.replace("git@github.com:", "https://github.com/")
    if cleaned.startswith("ssh://git@github.com/"):
        cleaned = cleaned.replace("ssh://git@github.com/", "https://github.com/")

    parsed = urlparse(cleaned)
    if parsed.netloc.lower() in {"github.com", "www.github.com"}:
        path = parsed.path.strip("/")
        path = path.removesuffix(".git")
        return path

    match = re.match(r"https?://(?:www\.)?github\.com/(?P<slug>[^\s]+?)(?:\.git)?/?$", cleaned)
    if match:
        return match.group("slug").strip("/")

    raise ValueError(f"Unsupported GitHub repository URL: {repo_url}")


def sync_github_repo_dependabot_alerts(repository: Repository, github_client=None) -> list[RepositoryAdvisory]:
    """Synchronise the repository's dependabot alerts to local RepositoryAdvisory records.
    Open advisories are created or refreshed. Advisories no longer open in GitHub are deleted.
    """
    if not repository.url:
        return []

    if github_client is not None:
        client = github_client
    elif os.getenv("GITHUB_TOKEN"):
        client = Github(auth=Token(os.getenv("GITHUB_TOKEN")))
    else:
        client = Github()

    repo_slug = _parse_github_repo_slug(repository.url)
    github_repo = client.get_repo(repo_slug)

    current_open_ghsa_ids: set[str] = set()
    saved_alerts: list[RepositoryAdvisory] = []

    for alert in github_repo.get_dependabot_alerts(state="open"):
        alert_data = getattr(alert, "raw_data", None) or getattr(alert, "_rawData", None) or {}
        security_advisory = alert_data.get("security_advisory") or {}
        ghsa_id = security_advisory.get("ghsa_id")

        if not ghsa_id:
            continue

        current_open_ghsa_ids.add(ghsa_id)
        advisory, created = RepositoryAdvisory.objects.get_or_create(
            guid=ghsa_id,
            defaults={
                "repository": repository,
                "data": alert_data,
                "severity": security_advisory.get("severity"),
            },
        )

        if not created:
            needs_update = (
                advisory.repository_id != repository.pk
                or advisory.data != alert_data
                or advisory.severity != security_advisory.get("severity")
            )
            if needs_update:
                advisory.repository = repository
                advisory.data = alert_data
                advisory.severity = security_advisory.get("severity")
                advisory.save(update_fields=["repository", "data", "severity"])

        saved_alerts.append(advisory)

    stale_advisories = RepositoryAdvisory.objects.filter(repository=repository).exclude(guid__in=current_open_ghsa_ids)
    stale_advisories.delete()

    return saved_alerts
