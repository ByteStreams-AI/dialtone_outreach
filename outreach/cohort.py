"""cohort.py — Lock a frozen batch of contacts for the live cohort send.

Milestone 2 step 4 in ``docs/project-status.md`` requires reviewers to
freeze a contact list before the first live send. Rather than introducing
a new Supabase table for what is essentially an ephemeral, local
review-time artifact, this module persists cohorts as JSON files under
``developer/cohorts/`` (which is gitignored).

A cohort file looks like::

    {
      "name": "batch-1",
      "created_at": "2026-05-01T17:32:00+00:00",
      "limit": 5,
      "contact_ids": ["…", "…"],
      "preview": [
        {"id": "…", "restaurant_name": "…", "owner_email": "…", "seq": 1,
         "subject": "Friday nights at …"}
      ]
    }

The runner can then load the cohort and restrict its send set to the
frozen ``contact_ids``. Once a cohort has shipped, ``unlock`` removes the
file so a stale snapshot can't accidentally be re-used.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from outreach import db, sequence
from outreach.templates import render_email

COHORT_DIR: Path = Path(__file__).resolve().parent.parent / "developer" / "cohorts"


@dataclass
class Cohort:
    """In-memory representation of a locked cohort.

    Attributes:
        name: Operator-supplied identifier (used as the JSON filename).
        created_at: ISO-8601 UTC timestamp of when the lock was created.
        limit: Number of contacts the lock was created with.
        contact_ids: Ordered list of Supabase ``contacts.id`` UUIDs.
        preview: Lightweight per-contact summary for human review.
    """

    name: str
    created_at: str
    limit: int
    contact_ids: list[str]
    preview: list[dict[str, Any]] = field(default_factory=list)

    @property
    def path(self) -> Path:
        """Filesystem path the cohort would be persisted to."""
        return COHORT_DIR / f"{self.name}.json"

    def write(self) -> Path:
        """Persist this cohort to ``developer/cohorts/<name>.json``.

        Returns:
            The path the cohort was written to.
        """
        COHORT_DIR.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return self.path


def _slug(name: str) -> str:
    """Normalize a cohort name into a filesystem-safe slug.

    Args:
        name: Raw cohort name from the operator.

    Returns:
        A lowercased, dash-separated slug. Raises ``ValueError`` if the
        name reduces to an empty string.
    """
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in name.strip().lower())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    if not cleaned:
        raise ValueError(f"Cohort name {name!r} is not usable as a filename")
    return cleaned


def lock_cohort(name: str, limit: int) -> Cohort:
    """Snapshot the next ``limit`` due contacts into a locked cohort.

    Args:
        name: Cohort identifier (slugified before use).
        limit: Maximum number of contacts to include.

    Returns:
        The :class:`Cohort` that was written to disk.

    Raises:
        FileExistsError: If a cohort with the same slug already exists.
            Use :func:`unlock_cohort` first if you want to overwrite it.
    """
    slug = _slug(name)
    target = COHORT_DIR / f"{slug}.json"
    if target.exists():
        raise FileExistsError(
            f"Cohort {slug!r} already exists at {target}. Unlock it first."
        )

    client = db.get_client()
    due = sequence.get_contacts_due(client, limit=limit)

    preview: list[dict[str, Any]] = []
    contact_ids: list[str] = []
    for contact in due:
        seq_num = sequence.next_sequence_number(contact)
        if seq_num is None:
            continue
        rendered = render_email(
            sequence_number=seq_num,
            first_name=contact.get("owner_first", ""),
            restaurant_name=contact.get("restaurant_name", ""),
            city=contact.get("city", ""),
            to_email=contact.get("owner_email"),
        )
        contact_ids.append(contact["id"])
        preview.append(
            {
                "id": contact["id"],
                "restaurant_name": contact.get("restaurant_name"),
                "owner_email": contact.get("owner_email"),
                "city": contact.get("city"),
                "lead_score": contact.get("lead_score"),
                "seq": seq_num,
                "subject": rendered["subject"],
            }
        )

    cohort = Cohort(
        name=slug,
        created_at=datetime.now(timezone.utc).isoformat(),
        limit=limit,
        contact_ids=contact_ids,
        preview=preview,
    )
    cohort.write()
    return cohort


def load_cohort(name: str) -> Cohort:
    """Load a previously-locked cohort by name.

    Args:
        name: Cohort identifier; slugified before lookup.

    Returns:
        The deserialized :class:`Cohort`.

    Raises:
        FileNotFoundError: If no cohort file exists for ``name``.
    """
    slug = _slug(name)
    path = COHORT_DIR / f"{slug}.json"
    if not path.exists():
        raise FileNotFoundError(f"No cohort named {slug!r} (looked at {path})")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Cohort(
        name=raw["name"],
        created_at=raw["created_at"],
        limit=int(raw.get("limit", 0)),
        contact_ids=list(raw.get("contact_ids", [])),
        preview=list(raw.get("preview", [])),
    )


def unlock_cohort(name: str) -> Optional[Path]:
    """Delete the cohort file for ``name``.

    Args:
        name: Cohort identifier; slugified before lookup.

    Returns:
        The deleted path, or ``None`` if no such cohort existed.
    """
    slug = _slug(name)
    path = COHORT_DIR / f"{slug}.json"
    if not path.exists():
        return None
    path.unlink()
    return path


def list_cohorts() -> list[Cohort]:
    """Return every cohort currently stored under ``COHORT_DIR``.

    Returns:
        A list of :class:`Cohort` objects, sorted by ``created_at``
        descending. Empty if the directory does not exist.
    """
    if not COHORT_DIR.exists():
        return []
    cohorts = []
    for entry in COHORT_DIR.glob("*.json"):
        try:
            cohorts.append(load_cohort(entry.stem))
        except Exception:
            continue
    cohorts.sort(key=lambda c: c.created_at, reverse=True)
    return cohorts
