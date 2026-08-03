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
    marketplace_providers: str | None = None  # e.g. "DoorDash, Uber Eats"
    first_party_ordering: str | None = None  # e.g. "ChowNow, Toast Online"
    email: str | None = None
    business_type: str | None = None  # food_truck | single_location | multi_location | enterprise
    website_url: str | None = None
    price_range: str | None = None  # $, $$, $$$, $$$$
    yelp_rating: float | None = None
    yelp_review_count: int | None = None
