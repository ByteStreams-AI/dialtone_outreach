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
        "email": lead.email or None,
        "delivery_platforms": lead.delivery_platforms or None,
        "marketplace_providers": lead.marketplace_providers or None,
        "first_party_ordering": lead.first_party_ordering or None,
        "notes": lead.notes or None,
        "price_range": lead.price_range,
        "yelp_rating": lead.yelp_rating,
        "yelp_review_count": lead.yelp_review_count,
    }


def _filter_conflicting_rows(rows: list[dict], existing_rows: list[dict]) -> tuple[list[dict], int]:
    """Drop rows whose phone is already owned by a different lead."""
    existing_phone_owners = {
        row["phone"]: (row.get("business_name"), row.get("city"))
        for row in existing_rows
        if row.get("phone")
    }
    seen_phones: set[str] = set()
    seen_identities: set[tuple[str, str]] = set()
    filtered = []
    skipped = 0

    for row in rows:
        identity = (row["business_name"], row["city"])
        phone = row.get("phone")
        phone_owner = existing_phone_owners.get(phone) if phone else None

        if identity in seen_identities or (phone and phone in seen_phones):
            skipped += 1
            continue
        if phone_owner and phone_owner != identity:
            skipped += 1
            continue

        filtered.append(row)
        seen_identities.add(identity)
        if phone:
            seen_phones.add(phone)

    return filtered, skipped


def upsert_leads(leads: Sequence[LeadItem]) -> tuple[int, int]:
    """Insert new leads into Supabase, deduplicating on (business_name, city).

    Existing rows are never overwritten by a re-scrape. business_type and
    website_url may be added only when the DB row currently has NULL.

    Returns (inserted_or_updated, skipped_blank) counts.
    """
    client = _get_client()

    rows = []
    skipped = 0
    leads_with_type: list[LeadItem] = []
    leads_with_website: list[LeadItem] = []
    leads_with_email: list[LeadItem] = []
    leads_with_marketplace: list[LeadItem] = []
    leads_with_first_party: list[LeadItem] = []

    for lead in leads:
        if not lead.name.strip() or not lead.city:
            skipped += 1
            continue
        rows.append(_lead_to_row(lead))
        if lead.business_type:
            leads_with_type.append(lead)
        if lead.website_url:
            leads_with_website.append(lead)
        if lead.email:
            leads_with_email.append(lead)
        if lead.marketplace_providers:
            leads_with_marketplace.append(lead)
        if lead.first_party_ordering:
            leads_with_first_party.append(lead)

    if not rows:
        return 0, skipped

    phones = [row["phone"] for row in rows if row["phone"]]
    existing_rows = []
    if phones:
        response = (
            client.table("leads").select("business_name,city,phone").in_("phone", phones).execute()
        )
        existing_rows = response.data or []

    rows, skipped_conflicts = _filter_conflicting_rows(rows, existing_rows)
    skipped += skipped_conflicts
    if not rows:
        return 0, skipped

    # Step 1: insert new rows without changing existing CRM records
    response = (
        client.table("leads")
        .upsert(rows, on_conflict="business_name,city", ignore_duplicates=True)
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

    # Step 4: set email only where it is still NULL
    for lead in leads_with_email:
        (
            client.table("leads")
            .update({"email": lead.email})
            .eq("business_name", lead.name)
            .eq("city", lead.city)
            .is_("email", "null")
            .execute()
        )

    # Step 5: set marketplace_providers only where it is still NULL
    for lead in leads_with_marketplace:
        (
            client.table("leads")
            .update({"marketplace_providers": lead.marketplace_providers})
            .eq("business_name", lead.name)
            .eq("city", lead.city)
            .is_("marketplace_providers", "null")
            .execute()
        )

    # Step 6: set first_party_ordering only where it is still NULL
    for lead in leads_with_first_party:
        (
            client.table("leads")
            .update({"first_party_ordering": lead.first_party_ordering})
            .eq("business_name", lead.name)
            .eq("city", lead.city)
            .is_("first_party_ordering", "null")
            .execute()
        )

    return written, skipped


def insert_lead(data: dict) -> dict:
    """Insert a single manually-entered lead row. Returns the created row."""
    client = _get_client()
    response = client.table("leads").insert(data).execute()
    return response.data[0] if response.data else {}
