"""Adapter classes for site-specific lead extraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from .models import LeadItem
from .parser import parse_listing_page


class ScraperAdapter(ABC):
    """Base interface for a source adapter."""

    @abstractmethod
    def matches(self, url: str, html: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def extract(self, html: str, source_url: str, limit: int = 20) -> List[LeadItem]:
        raise NotImplementedError


class SimpleListingAdapter(ScraperAdapter):
    """Fallback adapter for generic listing pages."""

    def matches(self, url: str, html: str) -> bool:
        normalized = html.lower()
        return normalized.count("<a ") >= 10 or "<article" in normalized or "<li" in normalized

    def extract(self, html: str, source_url: str, limit: int = 20) -> List[LeadItem]:
        return parse_listing_page(html, source_url=source_url, limit=limit)


DEFAULT_ADAPTERS: list[ScraperAdapter] = [SimpleListingAdapter()]


def get_adapter_for_url(url: str, html: str) -> ScraperAdapter | None:
    for adapter in DEFAULT_ADAPTERS:
        if adapter.matches(url, html):
            return adapter
    return None
