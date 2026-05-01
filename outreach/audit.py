"""audit.py — Reply-status mismatch detection and repair.

Surfaces contacts where ``email_log.replied_at`` is set but
``contacts.status`` hasn't been flipped to a terminal value (or vice
versa). This catches cases where a ``check-replies`` run failed
partway through, or where a manual Supabase edit left the two tables
out of sync.

Usage::

    python cli.py check-replies --audit [--fix]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from rich import box
from rich.console import Console
from rich.table import Table
from supabase import Client

from outreach import db
from outreach.config import Status

console = Console()


@dataclass
class Mismatch:
    """A single reply-status mismatch.

    Attributes:
        contact_id: UUID of the contact.
        restaurant_name: For display.
        owner_email: For display.
        current_status: The contact's current ``status`` value.
        has_replied_log: Whether any ``email_log`` row has
            ``replied_at`` set for this contact.
    """

    contact_id: str
    restaurant_name: Optional[str]
    owner_email: Optional[str]
    current_status: str
    has_replied_log: bool


@dataclass
class AuditResult:
    """Summary returned by :func:`run_audit`.

    Attributes:
        mismatches: List of detected mismatches.
        fixed: Number of mismatches corrected (only when ``fix=True``).
    """

    mismatches: list[Mismatch] = field(default_factory=list)
    fixed: int = 0


def run_audit(client: Client, *, fix: bool = False) -> AuditResult:
    """Find and optionally fix reply-status mismatches.

    A mismatch is a contact where ``email_log.replied_at`` is set on at
    least one row but ``contacts.status`` is not ``replied`` (or another
    terminal status). This means the sequence engine might keep emailing
    someone who has already replied.

    Args:
        client: Supabase client.
        fix: If ``True``, update each mismatched contact's status to
            ``replied``. If ``False``, only report.

    Returns:
        An :class:`AuditResult` with the detected mismatches and fix count.
    """
    result = AuditResult()
    rows = db.find_reply_status_mismatches(client)

    for row in rows:
        mismatch = Mismatch(
            contact_id=row["id"],
            restaurant_name=row.get("restaurant_name"),
            owner_email=row.get("owner_email"),
            current_status=row.get("status", "—"),
            has_replied_log=True,
        )
        result.mismatches.append(mismatch)

        if fix:
            db.mark_contact_replied(client, row["id"])
            result.fixed += 1

    return result


def print_audit_report(result: AuditResult, *, fix: bool = False) -> None:
    """Render the audit result as a Rich table.

    Args:
        result: The :class:`AuditResult` to display.
        fix: Whether fixes were applied (affects the summary line).
    """
    if not result.mismatches:
        console.print(
            "\n[green]✓[/green] No reply-status mismatches found.\n"
        )
        return

    table = Table(
        title="Reply-Status Mismatches",
        box=box.SIMPLE,
    )
    table.add_column("Restaurant", style="cyan")
    table.add_column("Owner Email", style="white")
    table.add_column("Status", style="yellow")
    table.add_column("email_log.replied_at", justify="center")
    table.add_column("Action", style="green" if fix else "dim")

    for m in result.mismatches:
        table.add_row(
            m.restaurant_name or "—",
            m.owner_email or "—",
            m.current_status,
            "✓" if m.has_replied_log else "—",
            "→ replied" if fix else "(needs --fix)",
        )

    console.print(table)

    if fix:
        console.print(
            f"\n[green]✓[/green] Fixed {result.fixed} mismatch(es).\n"
        )
    else:
        console.print(
            f"\n[yellow]![/yellow] {len(result.mismatches)} mismatch(es) found. "
            "Run with [bold]--fix[/bold] to correct them.\n"
        )
