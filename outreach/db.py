"""
db.py — Supabase client and all database operations
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from supabase import create_client, Client
from outreach.config import SUPABASE_URL, SUPABASE_SERVICE_KEY, TERMINAL_STATUSES, Status


def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ── Contacts ──────────────────────────────────────────────────────

def upsert_contact(client: Client, data: dict) -> dict:
    """
    Insert or update a contact keyed on domain.
    Returns the upserted row.
    """
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = (
        client.table("contacts")
        .upsert(data, on_conflict="domain")
        .execute()
    )
    return result.data[0] if result.data else {}


def get_contact(client: Client, contact_id: str) -> Optional[dict]:
    result = (
        client.table("contacts")
        .select("*")
        .eq("id", contact_id)
        .single()
        .execute()
    )
    return result.data


def get_contacts_due_for_outreach(client: Client, limit: int = 20) -> list[dict]:
    """
    Returns contacts that are eligible for the next email in their sequence.
    Excludes terminal statuses and contacts with no owner_email.
    Ordered by lead_score DESC so hottest leads go first.
    """
    result = (
        client.table("contacts_due_for_outreach")
        .select("*")
        .limit(limit)
        .execute()
    )
    return result.data or []


def update_contact_status(client: Client, contact_id: str, status: str) -> None:
    client.table("contacts").update({
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", contact_id).execute()


def mark_contact_replied(client: Client, contact_id: str) -> None:
    client.table("contacts").update({
        "status": Status.REPLIED,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", contact_id).execute()


def unsubscribe_contact(
    client: Client,
    contact_id: str,
    *,
    note: Optional[str] = None,
) -> dict:
    """Mark a contact as unsubscribed (CAN-SPAM honor obligation).

    Sets ``status`` to :attr:`Status.NOT_INTERESTED` (a terminal status
    that ``contacts_due_for_outreach`` already excludes) and appends an
    ``Unsubscribed YYYY-MM-DD`` line to the contact's ``notes`` field so
    prior context (lead notes, demo prep) is preserved.

    Args:
        client: Supabase client.
        contact_id: UUID of the row to update.
        note: Optional free-form note appended after the standard
            ``Unsubscribed`` audit line (e.g. the source of the request).

    Returns:
        The updated contact row, or ``{}`` if Supabase returned no data.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    audit_line = f"Unsubscribed {today}"
    if note:
        audit_line = f"{audit_line} — {note}"

    existing = (
        client.table("contacts")
        .select("notes")
        .eq("id", contact_id)
        .single()
        .execute()
    ).data or {}
    prior_notes = (existing.get("notes") or "").strip()
    merged_notes = (
        f"{prior_notes}\n{audit_line}".strip() if prior_notes else audit_line
    )

    result = (
        client.table("contacts")
        .update({
            "status": Status.NOT_INTERESTED,
            "notes": merged_notes,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", contact_id)
        .execute()
    )
    return (result.data or [{}])[0]


def get_all_contacts(client: Client) -> list[dict]:
    result = client.table("contacts").select("*").order("created_at", desc=True).execute()
    return result.data or []


def get_contacts_by_status(client: Client, status: str) -> list[dict]:
    result = (
        client.table("contacts")
        .select("*")
        .eq("status", status)
        .order("updated_at", desc=True)
        .execute()
    )
    return result.data or []


def find_contact_by_owner_email(client: Client, email: str) -> Optional[dict]:
    """Look up a single contact by ``owner_email``.

    Args:
        client: Supabase client.
        email: The owner email address to match (case-insensitive).

    Returns:
        The contact row dict, or ``None`` if no match is found.
    """
    result = (
        client.table("contacts")
        .select("*")
        .ilike("owner_email", email)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def find_reply_status_mismatches(client: Client) -> list[dict]:
    """Find contacts with a replied email but a non-terminal status.

    These are contacts where ``email_log.replied_at`` is set on at least
    one row but ``contacts.status`` has not been flipped to ``replied``
    (or another terminal status). This can happen if a webhook or
    ``check-replies`` run failed partway through.

    Returns:
        List of contact rows that need their status corrected.
    """
    # Pull all email_log rows that have replied_at set.
    replied_logs = (
        client.table("email_log")
        .select("contact_id")
        .not_.is_("replied_at", "null")
        .execute()
    ).data or []
    if not replied_logs:
        return []

    replied_contact_ids = list({row["contact_id"] for row in replied_logs})

    # Pull those contacts and filter to non-terminal statuses.
    contacts = (
        client.table("contacts")
        .select("*")
        .in_("id", replied_contact_ids)
        .execute()
    ).data or []

    return [
        c for c in contacts
        if c.get("status") not in TERMINAL_STATUSES
    ]


def search_contacts_by_domain(client: Client, domain: str) -> list[dict]:
    result = (
        client.table("contacts")
        .select("*")
        .ilike("domain", f"%{domain}%")
        .execute()
    )
    return result.data or []


# ── Email log ─────────────────────────────────────────────────────

def log_email_sent(
    client: Client,
    contact_id: str,
    sequence_number: int,
    subject: str,
    message_id: str = None,
) -> dict:
    row = {
        "contact_id":       contact_id,
        "sequence_number":  sequence_number,
        "subject":          subject,
        "message_id":       message_id,
        "sent_at":          datetime.now(timezone.utc).isoformat(),
    }
    result = client.table("email_log").insert(row).execute()
    return result.data[0] if result.data else {}


def mark_email_opened(client: Client, log_id: str) -> None:
    client.table("email_log").update({
        "opened_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", log_id).execute()


def mark_email_replied(client: Client, log_id: str) -> None:
    client.table("email_log").update({
        "replied_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", log_id).execute()


def mark_email_bounced(
    client: Client,
    log_id: str,
    bounce_type: Optional[str] = None,
) -> None:
    """Record a bounce notification for a previously-sent email.

    Args:
        client: Supabase client.
        log_id: ``email_log.id`` of the bounced message.
        bounce_type: Optional SES bounce classification
            (``"Permanent"``, ``"Transient"``, etc.).
    """
    payload = {"bounced_at": datetime.now(timezone.utc).isoformat()}
    if bounce_type:
        payload["bounce_type"] = bounce_type
    client.table("email_log").update(payload).eq("id", log_id).execute()


def mark_email_complained(
    client: Client,
    log_id: str,
    complaint_type: Optional[str] = None,
) -> None:
    """Record a SES complaint notification for a sent email.

    Args:
        client: Supabase client.
        log_id: ``email_log.id`` of the complained-about message.
        complaint_type: Optional SES complaint feedback type (e.g.
            ``"abuse"``, ``"fraud"``, ``"other"``).
    """
    payload = {"complained_at": datetime.now(timezone.utc).isoformat()}
    if complaint_type:
        payload["complaint_type"] = complaint_type
    client.table("email_log").update(payload).eq("id", log_id).execute()


def get_email_log_metrics(
    client: Client,
    *,
    since_iso: Optional[str] = None,
    contact_ids: Optional[list[str]] = None,
) -> dict:
    """Aggregate email-log counters for a time window or cohort.

    Args:
        client: Supabase client.
        since_iso: ISO-8601 timestamp; only messages sent at or after this
            instant are counted. ``None`` means all-time.
        contact_ids: Optional list of ``contacts.id`` values to restrict
            the aggregation to (used by the ``cohort metrics`` flow).

    Returns:
        A dict with the keys ``sent``, ``opened``, ``replied``,
        ``bounced``, and ``complained``.
    """
    query = client.table("email_log").select(
        "id, sent_at, opened_at, replied_at, bounced_at, complained_at"
    )
    if since_iso:
        query = query.gte("sent_at", since_iso)
    if contact_ids:
        query = query.in_("contact_id", contact_ids)
    rows = query.execute().data or []
    return {
        "sent":       len(rows),
        "opened":     sum(1 for r in rows if r.get("opened_at")),
        "replied":    sum(1 for r in rows if r.get("replied_at")),
        "bounced":    sum(1 for r in rows if r.get("bounced_at")),
        "complained": sum(1 for r in rows if r.get("complained_at")),
    }


def get_email_log_for_contact(client: Client, contact_id: str) -> list[dict]:
    result = (
        client.table("email_log")
        .select("*")
        .eq("contact_id", contact_id)
        .order("sent_at")
        .execute()
    )
    return result.data or []


def get_last_email_sent(client: Client, contact_id: str) -> Optional[dict]:
    result = (
        client.table("email_log")
        .select("*")
        .eq("contact_id", contact_id)
        .order("sent_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def contact_has_replied(client: Client, contact_id: str) -> bool:
    result = (
        client.table("email_log")
        .select("id")
        .eq("contact_id", contact_id)
        .not_.is_("replied_at", "null")
        .limit(1)
        .execute()
    )
    return bool(result.data)


# ── Stats ─────────────────────────────────────────────────────────

def get_status_counts(client: Client) -> dict:
    result = client.table("contact_status_counts").select("*").execute()
    return {row["status"]: row["count"] for row in (result.data or [])}


def get_emails_sent_today(client: Client) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    result = (
        client.table("email_log")
        .select("id", count="exact")
        .gte("sent_at", f"{today}T00:00:00+00:00")
        .execute()
    )
    return result.count or 0
