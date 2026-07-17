"""Runner logic for scraping and normalizing leads."""

from __future__ import annotations

from typing import Iterable

from .adapters import get_adapter_for_url
from .fetch import fetch_page
from .models import LeadItem


def scrape_url(url: str, limit: int = 20) -> list[LeadItem]:
    """Fetch a URL and extract a small batch of lead candidates."""

    html = fetch_page(url)
    adapter = get_adapter_for_url(url, html)
    if adapter is None:
        raise ValueError("no suitable scraper adapter found for URL")
    return adapter.extract(html, source_url=url, limit=limit)


def normalize_leads(items: Iterable[LeadItem]) -> list[LeadItem]:
    """Normalize scraped lead items into a consistent schema."""

    return [item for item in items if item.name and item.url]
