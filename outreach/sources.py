"""sources.py — Registry of import sources and their column mappings.

Kept in ``outreach/`` (rather than alongside ``scripts/import_contacts.py``)
so the CLI layer can import ``SOURCE_MAPS`` to drive ``--source`` choices
without pulling pandas / Supabase clients at module load. Adding a new
source means adding an entry to ``SOURCE_MAPS`` here — both
``scripts/import_contacts.py`` and ``cli.py`` pick it up automatically.

The canonical input contract (``REQUIRED_FIELDS``, ``CONTACT_COLUMNS``)
still lives in ``scripts/import_contacts.py`` since it is bound to the
import pipeline that consumes it.
"""
from __future__ import annotations


# Apollo CSV columns are lower-cased before mapping. We deliberately
# prefer the *company* address fields over the contact's personal
# city/state — outreach copy is about the restaurant location, not where
# the owner happens to live.
APOLLO_MAP: dict[str, str] = {
    "first name":        "owner_first",
    "last name":         "owner_last",
    "title":             "title",
    "email":             "owner_email",
    "work direct phone": "owner_phone",
    "company name":      "restaurant_name",
    "website":           "website",
    "company city":      "city",
    "company state":     "state",
    "company phone":     "business_phone",
    "company address":   "address",
}

# A "manual" source already speaks the canonical schema — no rename needed.
MANUAL_MAP: dict[str, str] = {}


SOURCE_MAPS: dict[str, dict[str, str]] = {
    "apollo": APOLLO_MAP,
    "manual": MANUAL_MAP,
}
