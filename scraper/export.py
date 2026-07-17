"""Export helpers for scraped lead data."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .models import LeadItem


def _serialize_bool(value: bool | None) -> str:
    if value is None:
        return ""
    return "yes" if value else "no"


def _existing_keys(path: Path) -> set[tuple[str, str]]:
    """Return (name, phone) pairs already present in a CSV file."""
    keys: set[tuple[str, str]] = set()
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                keys.add((row.get("name", "").strip().upper(), row.get("phone", "").strip()))
    except FileNotFoundError:
        pass
    return keys


def write_csv(path: str, leads: Iterable[LeadItem]) -> int:
    """Write leads to a CSV file, appending and deduplicating if it already exists.

    Returns the number of rows actually written.
    """
    fieldnames = [
        "name",
        "city",
        "source",
        "url",
        "phone",
        "address",
        "notes",
        "has_website",
        "has_app",
        "offers_pickup",
        "offers_delivery",
        "delivery_platforms",
        "uses_doordash_marketing",
        "uses_chownow",
    ]
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    append = out.exists()
    seen = _existing_keys(out) if append else set()
    written = 0
    with open(path, "a" if append else "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not append:
            writer.writeheader()
        for lead in leads:
            key = (lead.name.strip().upper(), (lead.phone or "").strip())
            if key in seen:
                continue
            seen.add(key)
            writer.writerow(
                {
                    "name": lead.name,
                    "city": lead.city or "",
                    "source": str(lead.source),
                    "url": str(lead.url),
                    "phone": lead.phone or "",
                    "address": lead.address or "",
                    "notes": lead.notes or "",
                    "has_website": _serialize_bool(lead.has_website),
                    "has_app": _serialize_bool(lead.has_app),
                    "offers_pickup": _serialize_bool(lead.offers_pickup),
                    "offers_delivery": _serialize_bool(lead.offers_delivery),
                    "delivery_platforms": lead.delivery_platforms or "",
                    "uses_doordash_marketing": _serialize_bool(lead.uses_doordash_marketing),
                    "uses_chownow": _serialize_bool(lead.uses_chownow),
                }
            )
            written += 1
    return written


def write_json(path: str, leads: Iterable[LeadItem]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    payload = [lead.model_dump(mode="json") for lead in leads]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
