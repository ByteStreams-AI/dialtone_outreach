"""Houston restaurant leads via the Yelp Fusion API.

Source: Yelp Fusion API — Business Search
Docs:   https://docs.developer.yelp.com/reference/v3_business_search
Auth:   Free API key from https://docs.developer.yelp.com/docs/fusion-intro
        Set the key in your environment:  YELP_API_KEY=<your-key>

Why Yelp:
  The City of Houston open data portal (data.houstontx.gov) hosts food
  establishment data only as XLSX files dated 2015 and earlier — too stale
  for outreach.  Yelp returns current business data including phone, address,
  and categories with a free 500-requests/day quota.

Free-tier limits:
  - 500 API calls per day
  - Up to 50 results per call; page with --offset in 50-unit steps
  - Max 1,000 results per location/category combo across offsets
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from .models import LeadItem

YELP_API_URL = "https://api.yelp.com/v3/businesses/search"

# Categories to request from Yelp.  Yelp applies these as OR filters.
YELP_CATEGORIES = "restaurants,food,foodtrucks"

# Yelp categories that we want to keep when filtering results.
# Checked against each business's category list (any match = include).
TARGET_CATEGORIES: set[str] = {
    "restaurants",
    "food",
    "foodtrucks",
    "foodstands",
    "cafes",
    "bakeries",
    "juicebars",
    "catering",
    "diners",
    "burgers",
    "pizza",
    "mexican",
    "bbq",
    "seafood",
    "sushi",
    "thai",
    "chinese",
    "italian",
    "american",
    "newamerican",
    "tradamerican",
    "tex-mex",
}


def _get_api_key() -> str:
    key = os.environ.get("YELP_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "YELP_API_KEY is not set.\n"
            "  1. Get a free key at https://docs.developer.yelp.com/docs/fusion-intro\n"
            "  2. Add it to your environment:  export YELP_API_KEY=<your-key>\n"
            "  3. Or add it to a .env file:    YELP_API_KEY=<your-key>"
        )
    return key


def _business_to_lead(biz: dict[str, Any], source_url: str) -> LeadItem | None:
    name = (biz.get("name") or "").strip()
    if not name:
        return None

    yelp_url = biz.get("url") or source_url
    phone = (biz.get("display_phone") or biz.get("phone") or "").strip() or None

    loc = biz.get("location") or {}
    address_parts = [
        loc.get("address1") or "",
        loc.get("address2") or "",
        loc.get("city") or "",
        loc.get("state") or "",
        loc.get("zip_code") or "",
    ]
    address = ", ".join(p for p in address_parts if p).strip(", ") or None
    city = (loc.get("city") or "Houston").strip()

    cats = [c.get("alias", "") for c in (biz.get("categories") or [])]
    cat_note = ", ".join(c.get("title", "") for c in (biz.get("categories") or []))

    # Rough call-prep signals from Yelp data
    has_website = None  # Yelp basic search doesn't return website URL
    offers_delivery = None
    offers_pickup = None
    if biz.get("transactions"):
        transactions: list[str] = biz["transactions"]
        offers_delivery = "delivery" in transactions
        offers_pickup = "pickup" in transactions or "restaurant_reservation" in transactions

    return LeadItem(
        name=name,
        source=source_url,
        url=yelp_url,
        city=city,
        phone=phone,
        address=address,
        notes=cat_note or None,
        has_website=has_website,
        has_app=None,
        offers_pickup=offers_pickup,
        offers_delivery=offers_delivery,
        delivery_platforms="Yelp" if offers_delivery else None,
    )


def scrape_houston(
    limit: int = 50,
    offset: int = 0,
    location: str = "Houston, TX",
    api_key: str | None = None,
) -> list[LeadItem]:
    """Fetch Houston restaurant leads from the Yelp Fusion API.

    Args:
        limit: Number of businesses to return (max 50 per Yelp call).
        offset: Pagination offset (increment by 50 for next page).
        location: Yelp location string.
        api_key: Override YELP_API_KEY env var (useful for testing).

    Returns:
        List of LeadItem records.

    Raises:
        ValueError: If YELP_API_KEY is not set and no api_key arg given.
        httpx.HTTPStatusError: On Yelp API errors (401 = bad key, 429 = rate limit).
    """
    key = api_key or _get_api_key()

    params: dict[str, Any] = {
        "location": location,
        "categories": YELP_CATEGORIES,
        "limit": min(limit, 50),
        "offset": offset,
        "sort_by": "best_match",
    }

    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }

    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        response = client.get(YELP_API_URL, params=params, headers=headers)
        response.raise_for_status()

    data = response.json()
    businesses: list[dict[str, Any]] = data.get("businesses", [])

    leads: list[LeadItem] = []
    seen: set[str] = set()

    for biz in businesses:
        lead = _business_to_lead(biz, YELP_API_URL)
        if lead is None:
            continue
        key_str = lead.name.lower()
        if key_str in seen:
            continue
        seen.add(key_str)
        leads.append(lead)

    return leads
