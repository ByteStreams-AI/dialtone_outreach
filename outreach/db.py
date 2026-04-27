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
