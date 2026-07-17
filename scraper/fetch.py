"""HTTP fetch helpers for scraper sources."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

DEFAULT_HEADERS = {
    "User-Agent": "lead-discovery-scraper/0.1 (+https://example.com)",
}


class ScraperFetchError(Exception):
    pass


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(httpx.HTTPError),
    reraise=True,
)
def fetch_page(url: str, timeout: float = 10.0) -> str:
    """Fetch a page and return its HTML content."""

    try:
        with httpx.Client(
            headers=DEFAULT_HEADERS, timeout=timeout, follow_redirects=True
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text
    except httpx.HTTPError as exc:
        raise ScraperFetchError(f"failed to fetch {url}: {exc}") from exc


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(httpx.HTTPError),
    reraise=True,
)
def fetch_json(
    url: str, params: dict[str, Any] | None = None, timeout: float = 10.0
) -> list[dict[str, Any]]:
    """Fetch a JSON endpoint and return a list of records."""

    try:
        with httpx.Client(
            headers=DEFAULT_HEADERS, timeout=timeout, follow_redirects=True
        ) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                return data
            return [data]
    except httpx.HTTPError as exc:
        raise ScraperFetchError(f"failed to fetch {url}: {exc}") from exc
