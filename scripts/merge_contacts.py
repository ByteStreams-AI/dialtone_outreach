"""
scripts/merge_contacts.py
--------------------------
Domain-match Outscraper restaurant records with Apollo owner records.
Updates owner_first, owner_last, owner_email, owner_phone on contacts
that have a matching domain in the Apollo import.

Usage:
    python scripts/merge_contacts.py
    python scripts/merge_contacts.py --dry-run
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import click
from rich.console import Console
from rich.progress import track
from outreach.db import get_client

console = Console()


@click.command()
@click.option("--dry-run", is_flag=True, default=False,
              help="Preview matches without writing to Supabase")
def main(dry_run):
    console.print(f"\n[bold blue]DialTone Contact Merger[/bold blue]  "
                  f"{'[yellow]DRY RUN[/yellow]' if dry_run else '[green]LIVE[/green]'}\n")

    client = get_client()

    # Pull all contacts
    all_contacts = client.table("contacts").select("*").execute().data or []

    # Separate by source
    outscraper = {c["domain"]: c for c in all_contacts
                  if c.get("source") == "outscraper" and c.get("domain")}
    apollo     = {c["domain"]: c for c in all_contacts
                  if c.get("source") == "apollo" and c.get("domain")}

    console.print(f"Outscraper records: [bold]{len(outscraper)}[/bold]")
    console.print(f"Apollo records:     [bold]{len(apollo)}[/bold]\n")

    matched = unmatched = updated = 0

    for domain, restaurant in track(outscraper.items(),
                                    total=len(outscraper),
                                    description="Matching..."):
        if domain not in apollo:
            unmatched += 1
            continue

        owner = apollo[domain]
        matched += 1

        # Only update if owner fields are currently empty
        needs_update = (
            not restaurant.get("owner_email") and owner.get("owner_email")
        )

        if not needs_update:
            continue

        patch = {}
        for field in ["owner_first","owner_last","owner_email","owner_phone"]:
            if owner.get(field) and not restaurant.get(field):
                patch[field] = owner[field]

        if not patch:
            continue

        if dry_run:
            console.print(
                f"  [dim]→[/dim] [cyan]{restaurant.get('restaurant_name')}[/cyan]  "
                f"domain={domain}  "
                f"would add: {list(patch.keys())}"
            )
            updated += 1
            continue

        try:
            client.table("contacts").update(patch).eq("id", restaurant["id"]).execute()
            console.print(
                f"  [green]✓[/green] [cyan]{restaurant.get('restaurant_name')}[/cyan]  "
                f"added owner: {owner.get('owner_first','')} {owner.get('owner_last','')}  "
                f"{owner.get('owner_email','')}"
            )
            updated += 1
        except Exception as e:
            console.print(f"  [red]✗[/red] {domain}: {e}")

    console.print(f"\n[bold]Merge complete.[/bold]")
    console.print(f"  Matched:   [green]{matched}[/green]")
    console.print(f"  Unmatched: [yellow]{unmatched}[/yellow]")
    console.print(f"  Updated:   [green]{updated}[/green]\n")


if __name__ == "__main__":
    main()
