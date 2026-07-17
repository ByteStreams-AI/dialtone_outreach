"""Supabase upsert helpers for lead data."""

from __future__ import annotations

import os
from typing import Sequence

from supabase import Client, create_client

from .models import LeadItem


def _get_client() -> Client:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in your environment or .env file."
        )
    return create_client(url, key)


def _lead_to_row(lead: LeadItem) -> dict:
    """Map a LeadItem to the leads table column names.

    business_type and website_url are intentionally excluded here — they are
    written separately via conditional UPDATEs so that user overrides in the
    CRM are never clobbered by a re-scrape.
    """
    return {
        "business_name": lead.name,
        "phone": lead.phone or None,
        "address": lead.address or None,
        "city": lead.city or None,
        "source_url": str(lead.source),
        "scrape_source": "yelp",
        "has_website": lead.has_website,
        "has_app": lead.has_app,
        "offers_delivery": lead.offers_delivery,
        "offers_pickup": lead.offers_pickup,
        "delivery_platforms": lead.delivery_platforms or None,
        "uses_doordash_mktg": lead.uses_doordash_marketing,
        "uses_chownow": lead.uses_chownow,
        "notes": lead.notes or None,
        "price_range": lead.price_range,
        "yelp_rating": lead.yelp_rating,
        "yelp_review_count": lead.yelp_review_count,
    }


def upsert_leads(leads: Sequence[LeadItem]) -> tuple[int, int]:
    """Upsert leads into Supabase, deduplicating on (business_name, city).

    business_type and website_url are written only when the DB row currently
    has NULL — preserving any manual overrides made in the CRM.

    Returns (inserted_or_updated, skipped_blank) counts.
    """
    client = _get_client()

    rows = []
    skipped = 0
    leads_with_type: list[LeadItem] = []
    leads_with_website: list[LeadItem] = []

    for lead in leads:
        if not lead.name.strip() or not lead.city:
            skipped += 1
            continue
        rows.append(_lead_to_row(lead))
        if lead.business_type:
            leads_with_type.append(lead)
        if lead.website_url:
            leads_with_website.append(lead)

    if not rows:
        return 0, skipped

    # Step 1: upsert all fields except business_type
    response = (
        client.table("leads")
        .upsert(rows, on_conflict="business_name,city", ignore_duplicates=False)
        .execute()
    )
    written = len(response.data) if response.data else 0

    # Step 2: set business_type only where it is still NULL
    for lead in leads_with_type:
        (
            client.table("leads")
            .update({"business_type": lead.business_type})
            .eq("business_name", lead.name)
            .eq("city", lead.city)
            .is_("business_type", "null")
            .execute()
        )

    # Step 3: set website_url only where it is still NULL
    for lead in leads_with_website:
        (
            client.table("leads")
            .update({"website_url": lead.website_url})
            .eq("business_name", lead.name)
            .eq("city", lead.city)
            .is_("website_url", "null")
            .execute()
        )

    return written, skipped
