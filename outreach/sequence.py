"""
sequence.py — Determines which contacts are due for which email today.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional
from outreach.config import (
    SEQUENCE_DELAYS, TERMINAL_STATUSES, SEQUENCE_STATUS_MAP, Status,
)
from outreach import db


def next_sequence_number(contact: dict) -> Optional[int]:
    """
    Given a contact's current status, return the next sequence number to send.
    Returns None if the contact should receive no further emails.
    """
    status = contact.get("status", Status.NEW)

    if status in TERMINAL_STATUSES:
        return None

    status_to_next = {
        Status.NEW:          1,
        Status.EMAILED_1:    2,
        Status.EMAILED_2:    3,
        Status.EMAILED_3:    4,
        Status.BREAKUP_SENT: 5,  # re-engage — only if opened
    }

    return status_to_next.get(status)


def is_due(contact: dict, client) -> bool:
    """
    Returns True if the contact is due for their next email today.
    """
    seq = next_sequence_number(contact)
    if seq is None:
        return False

    # Email #1 — eligible immediately if status is new
    if seq == 1:
        return True

    # For subsequent emails, check time elapsed since last send
    last = db.get_last_email_sent(client, contact["id"])
    if not last or not last.get("sent_at"):
        return False

    # Stop if they've replied at any point
    if db.contact_has_replied(client, contact["id"]):
        return False

    last_sent = datetime.fromisoformat(last["sent_at"])
    if last_sent.tzinfo is None:
        last_sent = last_sent.replace(tzinfo=timezone.utc)

    required_delay = SEQUENCE_DELAYS.get(seq, 999)
    elapsed_days   = (datetime.now(timezone.utc) - last_sent).days

    # Re-engage (seq 5) only fires if the breakup email was opened
    if seq == 5:
        opened = last.get("opened_at") is not None
        return elapsed_days >= required_delay and opened

    return elapsed_days >= required_delay


def get_contacts_due(client, limit: int = 20) -> list[dict]:
    """
    Returns up to `limit` contacts that are due for outreach today,
    ordered by lead_score descending.
    Only contacts with a valid owner_email are included.
    """
    # Pull all non-terminal contacts with an email address
    result = (
        client.table("contacts")
        .select("*")
        .not_.in_("status", list(TERMINAL_STATUSES))
        .not_.is_("owner_email", "null")
        .neq("owner_email", "")
        .order("lead_score", desc=True)
        .execute()
    )
    candidates = result.data or []

    due = []
    for contact in candidates:
        if is_due(contact, client):
            due.append(contact)
        if len(due) >= limit:
            break

    return due
