"""HTML parsing helpers for generic lead pages."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse
from typing import Iterable

from bs4 import BeautifulSoup

from .models import LeadItem


def _normalize_url(url: str, base_url: str) -> str:
    url = urljoin(base_url, url)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("unsupported URL scheme")
    return url


def parse_listing_page(html: str, source_url: str, limit: int = 20) -> list[LeadItem]:
    """Extract candidate leads from a listing page."""

    soup = BeautifulSoup(html, "lxml")
    leads: list[LeadItem] = []
    seen_urls: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        text = anchor.get_text(strip=True)
        if not text or len(text) < 5:
            continue

        try:
            href = _normalize_url(anchor["href"], source_url)
        except ValueError:
            continue

        if href in seen_urls:
            continue

        seen_urls.add(href)
        leads.append(
            LeadItem(
                name=text,
                source=source_url,
                url=href,
            )
        )
        if len(leads) >= limit:
            break

    return leads
