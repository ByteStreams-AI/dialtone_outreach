#!/usr/bin/env python3
"""
cli.py — DialTone Outreach CLI

Usage:
    python cli.py import --source outscraper --file export.csv
    python cli.py import --source apollo     --file export.csv
    python cli.py merge
    python cli.py run --dry-run
    python cli.py run
    python cli.py status
    python cli.py stats
    python cli.py contact --email owner@restaurant.com
    python cli.py send-test --to verified@inbox.com
"""
import click
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


@click.group()
def cli():
    """DialTone Outreach — Cold email sequencer for restaurant owners."""
    pass


# ── import ────────────────────────────────────────────────────────
@cli.command("import")
@click.option("--source", required=True,
              type=click.Choice(["outscraper", "apollo"], case_sensitive=False))
@click.option("--file",   required=True, type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, default=False)
def import_contacts(source, file, dry_run):
    """Import contacts from an Outscraper or Apollo CSV export."""
    from scripts.import_contacts import main as _import
    from click.testing import CliRunner
    # Pass args directly to the import script
    import sys, os
    sys.argv = ["import_contacts.py",
                "--source", source,
                "--file", file,
                *(["--dry-run"] if dry_run else [])]
    from scripts import import_contacts as ic
    ic.main(standalone_mode=False, args=[
        "--source", source, "--file", file,
        *(["--dry-run"] if dry_run else [])
    ])


# ── merge ─────────────────────────────────────────────────────────
@cli.command("merge")
@click.option("--dry-run", is_flag=True, default=False)
def merge(dry_run):
    """Domain-match Outscraper restaurants with Apollo owner contacts."""
    from scripts import merge_contacts as mc
    mc.main(standalone_mode=False, args=["--dry-run"] if dry_run else [])


# ── run ───────────────────────────────────────────────────────────
@cli.command("run")
@click.option("--dry-run", is_flag=True, default=False,
              help="Preview what would send without actually sending")
@click.option("--limit",   default=None, type=int,
              help="Override daily send limit for this run")
def run(dry_run, limit):
    """Send today's outreach emails."""
    from outreach.runner import run as _run
    _run(dry_run=dry_run, limit=limit)


# ── status ────────────────────────────────────────────────────────
@cli.command("status")
def status():
    """Print a status breakdown dashboard to the terminal."""
    from outreach.runner import print_status_dashboard
    print_status_dashboard()


# ── stats ─────────────────────────────────────────────────────────
@cli.command("stats")
def stats():
    """Print conversion rate statistics."""
    from outreach.db import get_client, get_status_counts, get_emails_sent_today
    client = get_client()
    counts = get_status_counts(client)
    today  = get_emails_sent_today(client)

    console.print("\n[bold blue]DialTone Outreach Stats[/bold blue]\n")
    console.print(f"  Emails sent today:  [bold]{today}[/bold]")

    total = sum(counts.values())
    sent  = sum(counts.get(s, 0) for s in
                ["emailed_1","emailed_2","emailed_3","breakup_sent"])
    demos    = counts.get("demo_booked", 0)
    pilots   = counts.get("pilot", 0)
    customers= counts.get("customer", 0)

    console.print(f"  Total contacts:     [bold]{total}[/bold]")
    console.print(f"  Emails sent:        [bold]{sent}[/bold]")
    console.print(f"  Demos booked:       [bold green]{demos}[/bold green]")
    console.print(f"  Pilots:             [bold blue]{pilots}[/bold blue]")
    console.print(f"  Customers:          [bold green]{customers}[/bold green]")

    if sent:
        console.print(f"\n  Email → Demo:     [bold]{demos/sent*100:.1f}%[/bold]  (target 3–6%)")
    if demos:
        console.print(f"  Demo  → Pilot:    [bold]{pilots/demos*100:.1f}%[/bold]  (target 30–50%)")
    if pilots:
        console.print(f"  Pilot → Customer: [bold]{customers/pilots*100:.1f}%[/bold]  (target 50–80%)")
    console.print()


# ── contact ───────────────────────────────────────────────────────
@cli.command("contact")
@click.option("--email",  default=None, help="Look up by owner email")
@click.option("--domain", default=None, help="Look up by domain")
def contact(email, domain):
    """Look up a contact and show their full outreach history."""
    from outreach.db import get_client, search_contacts_by_domain, get_email_log_for_contact
    client = get_client()

    if email:
        result = (client.table("contacts")
                  .select("*").eq("owner_email", email).execute())
        contacts = result.data or []
    elif domain:
        contacts = search_contacts_by_domain(client, domain)
    else:
        console.print("[red]Provide --email or --domain[/red]")
        return

    if not contacts:
        console.print("[yellow]No contact found.[/yellow]")
        return

    c = contacts[0]
    console.print(f"\n[bold cyan]{c.get('restaurant_name')}[/bold cyan]")
    console.print(f"  Domain:  {c.get('domain')}")
    console.print(f"  Phone:   {c.get('business_phone','—')}")
    console.print(f"  City:    {c.get('city','—')}, {c.get('state','—')}")
    console.print(f"  Owner:   {c.get('owner_first','')} {c.get('owner_last','')}  {c.get('owner_email','—')}")
    console.print(f"  Status:  [bold]{c.get('status','—')}[/bold]")
    console.print(f"  Score:   {c.get('lead_score','—')}")
    console.print(f"  Notes:   {c.get('notes','—')}\n")

    log = get_email_log_for_contact(client, c["id"])
    if log:
        table = Table(title="Email History", box=box.SIMPLE)
        table.add_column("Seq",      style="dim")
        table.add_column("Subject",  style="cyan")
        table.add_column("Sent",     style="white")
        table.add_column("Opened",   style="green")
        table.add_column("Replied",  style="yellow")
        for entry in log:
            table.add_row(
                str(entry.get("sequence_number","—")),
                entry.get("subject","—")[:50],
                entry.get("sent_at","—")[:10] if entry.get("sent_at") else "—",
                "✓" if entry.get("opened_at") else "—",
                "✓" if entry.get("replied_at") else "—",
            )
        console.print(table)
    else:
        console.print("  No emails sent yet.")
    console.print()


# ── send-test ───────────────────────────────────────────────────────
@cli.command("send-test")
@click.option("--to", "to_email", required=True,
              help="Verified SES recipient inbox")
@click.option("--seq", default=1, type=click.IntRange(1, 5),
              help="Which template (1-5) to render and send")
@click.option("--first-name",      default="Sample",  show_default=True)
@click.option("--restaurant-name", default="Sample Bistro", show_default=True)
@click.option("--city",            default="Nashville", show_default=True)
@click.option("--yes", is_flag=True, default=False,
              help="Skip the confirmation prompt")
def send_test(to_email, seq, first_name, restaurant_name, city, yes):
    """Render a single template and send it to a verified inbox.

    Used for the milestone 1 acceptance step "test send to a verified
    inbox renders correctly in Gmail and Apple Mail". Renders a sample
    contact through the real ``render_email`` + SES path so what lands
    in the inbox matches what production sends.
    """
    from outreach.templates import render_email
    from outreach.email_client import send_email
    from outreach.config import FROM_EMAIL

    email = render_email(
        sequence_number = seq,
        first_name      = first_name,
        restaurant_name = restaurant_name,
        city            = city,
        to_email        = to_email,
    )

    console.print(f"\n[bold blue]send-test[/bold blue]  seq=[bold]{seq}[/bold]  to=[cyan]{to_email}[/cyan]")
    console.print(f"  Subject: [white]{email['subject']}[/white]\n")
    console.print(email["text"])

    if not yes:
        click.confirm(
            "\nSend this email through SES?",
            abort=True,
            default=False,
        )

    resp = send_email(
        to_email   = to_email,
        subject    = email["subject"],
        body_text  = email["text"],
        body_html  = email["html"],
        reply_to   = FROM_EMAIL,
    )
    console.print(f"  [green]✓[/green] sent  message_id=[dim]{resp.get('message_id')}[/dim]\n")


if __name__ == "__main__":
    cli()
