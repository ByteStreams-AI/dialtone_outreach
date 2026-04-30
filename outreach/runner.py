"""
runner.py — Orchestrates the daily outreach run.
"""
from __future__ import annotations
from datetime import datetime, timezone
from rich.console import Console
from rich.table import Table
from rich import box
from outreach import db, sequence, email_client
from outreach.templates import render_email
from outreach.config import (
    DAILY_SEND_LIMIT, SEQUENCE_STATUS_MAP, FROM_EMAIL,
)

console = Console()


def run(dry_run: bool = False, limit: int = None) -> dict:
    """
    Main entry point for the daily outreach run.

    dry_run: preview what would send without actually sending
    limit:   override DAILY_SEND_LIMIT for this run
    """
    client     = db.get_client()
    send_limit = limit or DAILY_SEND_LIMIT
    sent_today = db.get_emails_sent_today(client)
    remaining  = max(0, send_limit - sent_today)

    console.print(
        f"\n[bold blue]DialTone Outreach Runner[/bold blue]  "
        f"{'[yellow]DRY RUN[/yellow]' if dry_run else '[green]LIVE[/green]'}\n"
        f"Already sent today: [bold]{sent_today}[/bold]  "
        f"Limit: [bold]{send_limit}[/bold]  "
        f"Remaining budget: [bold]{remaining}[/bold]\n"
    )

    if remaining == 0:
        console.print("[yellow]Daily send limit reached. Nothing to do.[/yellow]")
        return {"sent": 0, "skipped": 0, "errors": 0}

    due = sequence.get_contacts_due(client, limit=remaining)

    if not due:
        console.print("[yellow]No contacts are due for outreach today.[/yellow]")
        return {"sent": 0, "skipped": 0, "errors": 0}

    console.print(f"[bold]{len(due)}[/bold] contact(s) due for outreach.\n")

    results = {"sent": 0, "skipped": 0, "errors": 0, "details": []}

    for contact in due:
        seq_num = sequence.next_sequence_number(contact)
        if seq_num is None:
            results["skipped"] += 1
            continue

        email_data = render_email(
            sequence_number  = seq_num,
            first_name       = contact.get("owner_first", ""),
            restaurant_name  = contact.get("restaurant_name", ""),
            city             = contact.get("city", ""),
            to_email         = contact.get("owner_email"),
        )

        row = {
            "contact_id":      contact["id"],
            "restaurant":      contact.get("restaurant_name"),
            "to_email":        contact.get("owner_email"),
            "seq_num":         seq_num,
            "subject":         email_data["subject"],
            "status":          "would_send" if dry_run else None,
        }

        if dry_run:
            console.print(
                f"  [dim]→[/dim] [cyan]{contact.get('restaurant_name')}[/cyan]  "
                f"seq=[bold]{seq_num}[/bold]  "
                f"to=[dim]{contact.get('owner_email')}[/dim]\n"
                f"    Subject: {email_data['subject']}"
            )
            results["sent"] += 1
            row["status"] = "dry_run"
            results["details"].append(row)
            continue

        # Live send
        try:
            resp = email_client.send_email(
                to_email   = contact["owner_email"],
                subject    = email_data["subject"],
                body_text  = email_data["text"],
                body_html  = email_data["html"],
                reply_to   = FROM_EMAIL,
            )
            # Log it
            db.log_email_sent(
                client,
                contact_id      = contact["id"],
                sequence_number = seq_num,
                subject         = email_data["subject"],
                message_id      = resp.get("message_id"),
            )
            # Update status
            new_status = SEQUENCE_STATUS_MAP[seq_num]
            db.update_contact_status(client, contact["id"], new_status)

            console.print(
                f"  [green]✓[/green] [cyan]{contact.get('restaurant_name')}[/cyan]  "
                f"seq=[bold]{seq_num}[/bold]  "
                f"→ {contact.get('owner_email')}"
            )
            results["sent"] += 1
            row["status"] = "sent"

        except Exception as e:
            console.print(
                f"  [red]✗[/red] [cyan]{contact.get('restaurant_name')}[/cyan]  "
                f"[red]{e}[/red]"
            )
            results["errors"] += 1
            row["status"] = f"error: {e}"

        results["details"].append(row)

    _print_summary(results, dry_run)
    return results


def _print_summary(results: dict, dry_run: bool) -> None:
    label = "DRY RUN SUMMARY" if dry_run else "RUN SUMMARY"
    console.print(f"\n[bold]{label}[/bold]")
    console.print(f"  Sent:    [green]{results['sent']}[/green]")
    console.print(f"  Skipped: [yellow]{results['skipped']}[/yellow]")
    console.print(f"  Errors:  [red]{results['errors']}[/red]\n")


def print_status_dashboard(client=None) -> None:
    """Print a status breakdown table to the terminal."""
    if client is None:
        client = db.get_client()

    counts = db.get_status_counts(client)
    total  = sum(counts.values())

    table = Table(
        title="DialTone Outreach Status",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold blue",
    )
    table.add_column("Status",  style="cyan",  no_wrap=True)
    table.add_column("Count",   style="bold",  justify="right")
    table.add_column("% Total", justify="right")

    order = [
        "new","emailed_1","emailed_2","emailed_3","breakup_sent",
        "re_engage","demo_booked","pilot","customer",
        "replied","not_interested","invalid",
    ]
    for s in order:
        count = counts.get(s, 0)
        pct   = f"{count/total*100:.1f}%" if total else "—"
        color = {
            "demo_booked": "green",
            "customer":    "green",
            "pilot":       "blue",
            "not_interested": "red",
            "replied":     "yellow",
        }.get(s, "white")
        table.add_row(s, str(count), pct, style=color if s in ("demo_booked","customer") else None)

    table.add_section()
    table.add_row("TOTAL", str(total), "100%", style="bold")

    console.print(table)

    # Conversion rates
    sent = sum(counts.get(s, 0) for s in ["emailed_1","emailed_2","emailed_3","breakup_sent"])
    demos    = counts.get("demo_booked", 0)
    pilots   = counts.get("pilot", 0)
    customers= counts.get("customer", 0)

    console.print("\n[bold]Conversion Rates[/bold]")
    console.print(f"  Email → Demo:    [bold]{demos/sent*100:.1f}%[/bold] ({demos}/{sent})  target: 3–6%" if sent else "  Email → Demo:    —")
    console.print(f"  Demo  → Pilot:   [bold]{pilots/demos*100:.1f}%[/bold] ({pilots}/{demos})  target: 30–50%" if demos else "  Demo  → Pilot:   —")
    console.print(f"  Pilot → Customer:[bold]{customers/pilots*100:.1f}%[/bold] ({customers}/{pilots})  target: 50–80%\n" if pilots else "  Pilot → Customer:—\n")
