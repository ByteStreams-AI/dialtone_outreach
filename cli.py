#!/usr/bin/env python3
"""Starter CLI for lead discovery and web scraping experiments."""

from __future__ import annotations

import click
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

from lead_tools.cli import render_leads, seed_demo_leads
from scraper import scrape_url
from scraper.db import upsert_leads
from scraper.export import write_csv, write_json
from scraper.houston import scrape_houston

console = Console()


@click.group()
def cli() -> None:
    """Lead discovery starter CLI."""


@cli.command("status")
def status() -> None:
    """Show the startup status of the scraper starter."""

    console.print("[bold green]Lead discovery scraper starter[/bold green]")
    console.print("- demo dataset available")
    console.print("- run `python cli.py scrape <url>` to extract lead candidates")
    console.print("- export supports website/app/pickup/delivery flags")


@cli.command("demo")
def demo() -> None:
    """Print a small built-in demo lead dataset."""

    leads = seed_demo_leads()
    console.print(render_leads(leads))


@cli.command("scrape")
@click.argument("url")
@click.option("--limit", default=20, type=int, help="Maximum number of leads to extract.")
@click.option("--export", type=click.Choice(["csv", "json"], case_sensitive=False), default=None)
@click.option("--output", type=click.Path(dir_okay=False, writable=True), default=None)
def scrape(url: str, limit: int, export: str | None, output: str | None) -> None:
    """Scrape a listing page and print extracted lead candidates."""

    console.print(f"[bold]Scraping:[/bold] {url}")
    try:
        leads = scrape_url(url, limit=limit)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise click.Abort()

    if not leads:
        console.print("[yellow]No leads were extracted.[/yellow]")
        return

    for lead in leads:
        console.print(
            f"- [cyan]{lead.name}[/cyan] | {lead.city or '—'} | {lead.url} | "
            f"website={bool(lead.has_website)} pickup={bool(lead.offers_pickup)}"
        )

    if export and output:
        from pathlib import Path

        if export.lower() == "csv":
            existing = Path(output).exists()
            written = write_csv(output, leads)
            skipped = len(leads) - written
            verb = "Appended" if existing else "Exported"
            suffix = (
                f" ({skipped} duplicate{'s' if skipped != 1 else ''} skipped)" if skipped else ""
            )
            console.print(f"[green]{verb}[/green] {written} leads \u2192 {output}{suffix}")
        else:
            write_json(output, leads)
            console.print(f"[green]Exported[/green] {len(leads)} leads \u2192 {output}")


@cli.command("scrape-houston")
@click.option(
    "--limit", default=50, type=int, help="Number of records to fetch (max 50 per Yelp call)."
)
@click.option(
    "--offset", default=0, type=int, help="Pagination offset (increment by 50 for next page)."
)
@click.option(
    "--api-key",
    default=None,
    envvar="YELP_API_KEY",
    help="Yelp Fusion API key (or set YELP_API_KEY env var).",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Optional CSV file path. Appends to existing file.",
)
@click.option("--no-db", is_flag=True, default=False, help="Skip Supabase upsert.")
def scrape_houston_cmd(
    limit: int, offset: int, api_key: str | None, output: str | None, no_db: bool
) -> None:
    """Fetch Houston restaurant leads from Yelp and upsert into Supabase.

    Requires a free Yelp API key — set YELP_API_KEY in .env or pass --api-key.
    Supabase credentials are read from SUPABASE_URL and SUPABASE_SERVICE_KEY in .env.

    Optionally write to a CSV file with --output leads.csv.
    """

    console.print(
        f"[bold]Fetching Houston restaurants via Yelp[/bold] (limit={limit}, offset={offset})"
    )
    try:
        leads = scrape_houston(limit=limit, offset=offset, api_key=api_key or None)
    except ValueError as exc:
        console.print(f"[red]Setup required:[/red] {exc}")
        raise click.Abort()
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise click.Abort()

    if not leads:
        console.print("[yellow]No leads returned.[/yellow]")
        return

    for lead in leads:
        console.print(f"- [cyan]{lead.name}[/cyan] | {lead.phone or '—'} | {lead.address or '—'}")

    console.print(f"\n[bold]{len(leads)}[/bold] leads fetched.")

    # ── Supabase upsert ────────────────────────────────────────────────────────
    if not no_db:
        try:
            written, skipped_blank = upsert_leads(leads)
            suffix = f" ({skipped_blank} skipped — missing name/city)" if skipped_blank else ""
            console.print(f"[green]Supabase:[/green] {written} rows upserted{suffix}")
        except ValueError as exc:
            console.print(f"[yellow]Supabase skipped:[/yellow] {exc}")
        except Exception as exc:
            console.print(f"[red]Supabase error:[/red] {exc}")

    # ── Optional CSV export ────────────────────────────────────────────────────
    if output:
        from pathlib import Path

        existing = Path(output).exists()
        written_csv = write_csv(output, leads)
        skipped_csv = len(leads) - written_csv
        verb = "Appended" if existing else "Exported"
        suffix = (
            f" ({skipped_csv} duplicate{'s' if skipped_csv != 1 else ''} skipped)"
            if skipped_csv
            else ""
        )
        console.print(f"[green]{verb}[/green] {written_csv} leads \u2192 {output}{suffix}")


if __name__ == "__main__":
    cli()
