"""Data models for scraper output."""

from __future__ import annotations

from pydantic import BaseModel, HttpUrl


class LeadItem(BaseModel):
    name: str
    source: HttpUrl
    url: HttpUrl
    city: str | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    has_website: bool | None = None
    has_app: bool | None = None
    offers_pickup: bool | None = None
    offers_delivery: bool | None = None
    delivery_platforms: str | None = None
    uses_doordash_marketing: bool | None = None
    uses_chownow: bool | None = None
