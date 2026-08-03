"""Google Maps lead discovery via the Apify Actor compass/crawler-google-places.

Source: Apify Google Maps Scraper
Docs:   https://apify.com/compass/crawler-google-places
Auth:   Apify API token from https://console.apify.com/account/integrations
        Set the token in your environment: APIFY_API_TOKEN=<your-token>

Pricing (Starter plan, $29/month):
  - ~$1.50 / 1,000 places scraped
  - scrapeContacts (email extraction) billed per place enriched
  - scrapeOrderOnline and scrapeTableReservationProvider included in base price
"""

from __future__ import annotations

import os
import urllib.parse
from typing import Any

import httpx
from apify_client import ApifyClient

from .enrich import detect_providers
from .models import LeadItem

ACTOR_ID = "compass/crawler-google-places"

# Provider name substrings → classified as marketplace (commission-based)
_MARKETPLACE_KEYWORDS = {"doordash", "uber eats", "grubhub", "seamless", "postmates"}
# Provider name substrings → classified as first-party (owned ordering)
_FIRST_PARTY_KEYWORDS = {"chownow", "toast", "square", "olo", "slice", "bopple", "flipdish"}


def _get_api_token() -> str:
    token = os.environ.get("APIFY_API_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "APIFY_API_TOKEN is not set.\n"
            "  1. Sign up at https://apify.com\n"
            "  2. Copy your token from console.apify.com/account/integrations\n"
            "  3. Add to .env:  APIFY_API_TOKEN=<your-token>"
        )
    return token


def _classify_providers(
    order_online: list[dict[str, Any]],
    reservation_provider: str | None,
) -> tuple[list[str], list[str]]:
    marketplace: list[str] = []
    first_party: list[str] = []
    seen: set[str] = set()

    for entry in order_online or []:
        # Guard: entry may be a string (provider name) or a dict with a "name" key
        if isinstance(entry, str):
            name = entry.strip()
        elif isinstance(entry, dict):
            name = (entry.get("name") or "").strip()
        else:
            continue
        if not name or name in seen:
            continue
        seen.add(name)
        lower = name.lower()
        if any(k in lower for k in _MARKETPLACE_KEYWORDS):
            marketplace.append(name)
        elif any(k in lower for k in _FIRST_PARTY_KEYWORDS):
            first_party.append(name)
        else:
            marketplace.append(name)  # unknown → assume marketplace for sales purposes

    if reservation_provider and reservation_provider not in seen:
        lower = reservation_provider.lower()
        if any(k in lower for k in _FIRST_PARTY_KEYWORDS):
            first_party.append(reservation_provider)
        else:
            first_party.append(reservation_provider)

    return marketplace, first_party


def _place_to_lead(item: dict[str, Any], source_url: str) -> LeadItem | None:
    name = (item.get("title") or "").strip()
    if not name:
        return None

    place_url = item.get("url") or source_url
    phone = (item.get("phoneUnformatted") or item.get("phone") or "").strip() or None
    address = (item.get("address") or "").strip() or None
    city = (item.get("city") or "").strip() or None
    website_url = (item.get("website") or "").strip() or None
    price_range = (item.get("price") or "").strip() or None

    # Email from scrapeContacts enrichment — field is a list, take first
    raw_emails: list[str] = item.get("emails") or []
    email = raw_emails[0].strip() if raw_emails else None

    # Categories are returned as a list of strings
    categories: list[str] = [c for c in (item.get("categories") or []) if isinstance(c, str)]
    cat_note = ", ".join(categories) if categories else (item.get("categoryName") or "")

    # food_truck detection from category names
    lower_cats = [c.lower() for c in categories]
    if any("food truck" in c or "foodtruck" in c for c in lower_cats):
        business_type: str | None = "food_truck"
    else:
        business_type = "single_location"

    # Delivery provider classification
    order_online: list[dict] = item.get("orderOnline") or []
    # tableReservationProvider may be a dict {"name": ...} or a plain string
    reservation_raw = (item.get("restaurantData") or {}).get("tableReservationProvider")
    if isinstance(reservation_raw, dict):
        reservation_provider = (reservation_raw.get("name") or "").strip() or None
    elif isinstance(reservation_raw, str):
        reservation_provider = reservation_raw.strip() or None
    else:
        reservation_provider = None
    marketplace, first_party = _classify_providers(order_online, reservation_provider)

    all_platforms = marketplace + [p for p in first_party if p not in marketplace]
    delivery_platforms = ", ".join(all_platforms) if all_platforms else None
    offers_delivery = bool(all_platforms) or None

    return LeadItem(
        name=name,
        source=source_url,
        url=place_url,
        city=city,
        phone=phone,
        address=address,
        email=email,
        notes=cat_note or None,
        has_website=bool(website_url),
        has_app=None,
        offers_pickup=None,
        offers_delivery=offers_delivery,
        delivery_platforms=delivery_platforms,
        marketplace_providers=", ".join(marketplace) if marketplace else None,
        first_party_ordering=", ".join(first_party) if first_party else None,
        business_type=business_type,
        website_url=website_url,
        price_range=price_range,
        yelp_rating=item.get("totalScore"),
        yelp_review_count=item.get("reviewsCount"),
    )


def scrape_google_maps(
    search_terms: list[str],
    location: str = "Houston, TX",
    limit: int = 50,
    api_token: str | None = None,
) -> list[LeadItem]:
    """Run the Apify Google Maps Scraper and return LeadItem results.

    Args:
        search_terms: Search queries, e.g. ["restaurant", "food truck"].
        location: Location string, e.g. "Houston, TX".
        limit: Max results per search term (Starter plan handles large numbers).
        api_token: Override APIFY_API_TOKEN env var.

    Returns:
        List of LeadItem records, deduplicated by name.

    Raises:
        ValueError: If APIFY_API_TOKEN is not set.
    """
    token = api_token or _get_api_token()
    apify = ApifyClient(token)

    query = urllib.parse.quote_plus(f"{search_terms[0]} {location}")
    source_url = f"https://www.google.com/maps/search/{query}"

    run_input = {
        "searchStringsArray": search_terms,
        "locationQuery": location,
        "maxCrawledPlacesPerSearch": limit,
        "language": "en",
        "scrapePlaceDetailPage": True,
        "scrapeOrderOnline": True,
        "scrapeTableReservationProvider": True,
        "scrapeContacts": True,
        "website": "allPlaces",
        "skipClosedPlaces": True,
    }

    run = apify.actor(ACTOR_ID).call(run_input=run_input)
    # apify-client v3 returns a typed Run object (not a dict)
    dataset_id = run.default_dataset_id

    leads: list[LeadItem] = []
    seen: set[str] = set()

    for item in apify.dataset(dataset_id).iterate_items():
        lead = _place_to_lead(item, source_url)
        if lead is None:
            continue
        key = lead.name.lower()
        if key in seen:
            continue
        seen.add(key)
        leads.append(lead)

    # Website enrichment: detect providers from the restaurant's own HTML
    with httpx.Client(timeout=10, follow_redirects=True) as web_client:
        for lead in leads:
            if not lead.website_url:
                continue
            mkt, fp = detect_providers(str(lead.website_url), web_client)
            if mkt or fp:
                lead.marketplace_providers = ", ".join(mkt) if mkt else None
                lead.first_party_ordering = ", ".join(fp) if fp else None

    return leads
