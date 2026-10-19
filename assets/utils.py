from typing import Callable
import requests
import json
import time

from django.utils.timezone import now

from assets.models import Asset


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
