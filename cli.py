#!/usr/bin/env python3
"""Starter CLI for lead discovery and web scraping experiments."""

from __future__ import annotations

import re

import click
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

from lead_tools.cli import render_leads, seed_demo_leads
from scraper import scrape_url
from scraper.db import upsert_leads
from scraper.export import write_csv, write_json
from scraper.apify_google_maps import scrape_google_maps
from scraper.houston import scrape_houston

console = Console()


def normalize_phone(phone: str | None) -> str | None:
    """Return a dialable tel URI, defaulting 10-digit numbers to US E.164."""
    if not phone or not phone.strip():
        return None

    value = phone.strip()
    if value.lower().startswith("tel:"):
        value = value[4:].strip()

    international = value.startswith("+") or value.startswith("00")
    digits = re.sub(r"\D", "", value)
    if value.startswith("00"):
        digits = digits[2:]

    if not 3 <= len(digits) <= 15:
        raise ValueError(f"Invalid phone number: {phone}")

    if international:
        if digits.startswith("0"):
            raise ValueError(f"Invalid international phone number: {phone}")
        return f"tel:+{digits}"
    if len(digits) == 10:
        return f"tel:+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"tel:+{digits}"
    return f"tel:{digits}"


def _normalize_lead_phones(leads: list) -> None:
    for lead in leads:
        try:
            lead.phone = normalize_phone(lead.phone)
        except ValueError:
            lead.phone = None


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

    _normalize_lead_phones(leads)
    for lead in leads:
        console.print(f"- [cyan]{lead.name}[/cyan] | {lead.phone or '—'} | {lead.address or '—'}")

    console.print(f"\n[bold]{len(leads)}[/bold] leads fetched.")

    # ── Supabase upsert ────────────────────────────────────────────────────────
    if not no_db:
        try:
            written, skipped_blank = upsert_leads(leads)
            suffix = (
                f" ({skipped_blank} skipped — duplicate or missing name/city)"
                if skipped_blank
                else ""
            )
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
        console.print(f"[green]{verb}[/green] {written_csv} leads → {output}{suffix}")


def _scrape_location_cmd(
    location: str,
    limit: int,
    offset: int,
    api_key: str | None,
    output: str | None,
    no_db: bool,
) -> None:
    """Shared implementation for all city scrape commands."""
    console.print(
        f"[bold]Fetching restaurants via Yelp[/bold] — {location} (limit={limit}, offset={offset})"
    )
    try:
        leads = scrape_houston(
            limit=limit, offset=offset, location=location, api_key=api_key or None
        )
    except ValueError as exc:
        console.print(f"[red]Setup required:[/red] {exc}")
        raise click.Abort()
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise click.Abort()

    if not leads:
        console.print("[yellow]No leads returned.[/yellow]")
        return

    _normalize_lead_phones(leads)
    for lead in leads:
        console.print(f"- [cyan]{lead.name}[/cyan] | {lead.phone or '—'} | {lead.address or '—'}")

    console.print(f"\n[bold]{len(leads)}[/bold] leads fetched.")

    if not no_db:
        try:
            written, skipped_blank = upsert_leads(leads)
            suffix = (
                f" ({skipped_blank} skipped — duplicate or missing name/city)"
                if skipped_blank
                else ""
            )
            console.print(f"[green]Supabase:[/green] {written} rows upserted{suffix}")
        except ValueError as exc:
            console.print(f"[yellow]Supabase skipped:[/yellow] {exc}")
        except Exception as exc:
            console.print(f"[red]Supabase error:[/red] {exc}")

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
        console.print(f"[green]{verb}[/green] {written_csv} leads → {output}{suffix}")


def _city_options(f: click.decorators.FC) -> click.decorators.FC:
    """Common options shared by all city scrape commands."""
    f = click.option(
        "--limit", default=50, type=int, help="Number of records to fetch (max 50 per Yelp call)."
    )(f)
    f = click.option(
        "--offset", default=0, type=int, help="Pagination offset (increment by 50 for next page)."
    )(f)
    f = click.option("--api-key", default=None, envvar="YELP_API_KEY", help="Yelp Fusion API key.")(
        f
    )
    f = click.option(
        "--output",
        type=click.Path(dir_okay=False, writable=True),
        default=None,
        help="Optional CSV file path.",
    )(f)
    f = click.option("--no-db", is_flag=True, default=False, help="Skip Supabase upsert.")(f)
    return f


@cli.command("scrape-city")
@click.option(
    "--location",
    required=True,
    help='Yelp location string, e.g. "Memphis, TN" or "Nashville, TN".',
)
@_city_options
def scrape_city_cmd(
    location: str, limit: int, offset: int, api_key: str | None, output: str | None, no_db: bool
) -> None:
    """Fetch restaurant leads for any city from Yelp and upsert into Supabase."""
    _scrape_location_cmd(location, limit, offset, api_key, output, no_db)


@cli.command("scrape-memphis")
@_city_options
def scrape_memphis_cmd(
    limit: int, offset: int, api_key: str | None, output: str | None, no_db: bool
) -> None:
    """Fetch Memphis, TN restaurant leads from Yelp and upsert into Supabase."""
    _scrape_location_cmd("Memphis, TN", limit, offset, api_key, output, no_db)


@cli.command("scrape-google-maps")
@click.option(
    "--search",
    "search_terms",
    multiple=True,
    default=["restaurant"],
    show_default=True,
    help='Search terms, e.g. --search restaurant --search "food truck".',
)
@click.option(
    "--location",
    default="Houston, TX",
    show_default=True,
    help="Location query, e.g. 'Houston, TX'.",
)
@click.option(
    "--limit", default=50, type=int, show_default=True, help="Max results per search term."
)
@click.option(
    "--api-token",
    default=None,
    envvar="APIFY_API_TOKEN",
    help="Apify API token (or set APIFY_API_TOKEN env var).",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Optional CSV file path.",
)
@click.option("--no-db", is_flag=True, default=False, help="Skip Supabase upsert.")
def scrape_google_maps_cmd(
    search_terms: tuple[str, ...],
    location: str,
    limit: int,
    api_token: str | None,
    output: str | None,
    no_db: bool,
) -> None:
    """Discover leads via Apify Google Maps Scraper and upsert into Supabase.

    Returns richer data than Yelp: email, confirmed delivery platforms,
    reservation system, and food truck detection. DB deduplication merges
    results with existing Yelp-sourced leads by (business_name, city).

    Requires APIFY_API_TOKEN in .env. Free plan: ~3,300 places/month.
    Starter plan ($29/mo): ~19,000 places/month.

    Examples:

      uv run python cli.py scrape-google-maps --location "Houston, TX"

      uv run python cli.py scrape-google-maps --search restaurant --search "food truck" --limit 100
    """
    console.print(
        f"[bold]Fetching via Apify Google Maps[/bold] — {location} "
        f"(terms={list(search_terms)}, limit={limit})"
    )
    try:
        leads = scrape_google_maps(
            search_terms=list(search_terms),
            location=location,
            limit=limit,
            api_token=api_token or None,
        )
    except ValueError as exc:
        console.print(f"[red]Setup required:[/red] {exc}")
        raise click.Abort()
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise click.Abort()

    if not leads:
        console.print("[yellow]No leads returned.[/yellow]")
        return

    _normalize_lead_phones(leads)
    for lead in leads:
        email_tag = f" | [green]{lead.email}[/green]" if lead.email else ""
        mkt = lead.marketplace_providers or "—"
        console.print(f"- [cyan]{lead.name}[/cyan] | {lead.phone or '—'} | mkt={mkt}{email_tag}")

    console.print(f"\n[bold]{len(leads)}[/bold] leads fetched.")

    if not no_db:
        try:
            written, skipped_blank = upsert_leads(leads)
            suffix = (
                f" ({skipped_blank} skipped — duplicate or missing name/city)"
                if skipped_blank
                else ""
            )
            console.print(f"[green]Supabase:[/green] {written} rows upserted{suffix}")
        except ValueError as exc:
            console.print(f"[yellow]Supabase skipped:[/yellow] {exc}")
        except Exception as exc:
            console.print(f"[red]Supabase error:[/red] {exc}")

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
        console.print(f"[green]{verb}[/green] {written_csv} leads → {output}{suffix}")


_BUSINESS_TYPE_CHOICES = (
    "food_truck",
    "single_location",
    "multi_configuration",
    "multi_location",
    "enterprise",
)


@cli.command("add-lead")
def add_lead_cmd() -> None:
    """Manually add a new lead record to Supabase."""
    from scraper.db import insert_lead

    console.rule("[bold]Add New Lead[/bold]")
    console.print(f"  {click.style('*', fg='red', bold=True)} = required\n")

    def _required(label: str) -> str:
        return click.style("* ", fg="red", bold=True) + label

    def _optional(label: str, hint: str = "") -> str:
        suffix = f" [{hint}]" if hint else " [optional]"
        return "  " + label + suffix

    def prompt_required(label: str) -> str:
        value = ""
        while not value:
            value = click.prompt(_required(label)).strip()
            if not value:
                console.print(f"[red]{label} is required.[/red]")
        return value

    # ── Required ──────────────────────────────────────────────────────────────
    business_name = prompt_required("Business Name")
    city = prompt_required("City")
    state = prompt_required("State")

    # ── Optional ──────────────────────────────────────────────────────────────
    while True:
        phone_input = click.prompt(_optional("Phone"), default="").strip() or None
        try:
            phone = normalize_phone(phone_input)
            break
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
    email = click.prompt(_optional("Email"), default="").strip() or None
    address = click.prompt(_optional("Address"), default="").strip() or None
    contact_name = click.prompt(_optional("Contact Name"), default="").strip() or None
    website_url = click.prompt(_optional("Website URL"), default="").strip() or None

    bt_hint = "/".join(_BUSINESS_TYPE_CHOICES)
    business_type_raw = (
        click.prompt(_optional("Business Type", bt_hint), default="").strip() or None
    )
    if business_type_raw and business_type_raw not in _BUSINESS_TYPE_CHOICES:
        console.print(
            f"[yellow]Warning:[/yellow] '{business_type_raw}' is not a recognized type. "
            f"Valid: {bt_hint}"
        )
        if not click.confirm("  Use it anyway?", default=False):
            business_type_raw = None

    notes = click.prompt(_optional("Notes"), default="").strip() or None

    # ── Summary ───────────────────────────────────────────────────────────────
    console.rule()
    fields = [
        ("Business Name", business_name),
        ("City", city),
        ("State", state),
        ("Phone", phone),
        ("Email", email),
        ("Address", address),
        ("Contact Name", contact_name),
        ("Website URL", website_url),
        ("Business Type", business_type_raw),
        ("Notes", notes),
    ]
    for label, value in fields:
        if value:
            console.print(f"  [bold]{label}:[/bold] {value}")
    console.rule()

    if not click.confirm("Save this lead?", default=True):
        console.print("[yellow]Cancelled.[/yellow]")
        return

    row = {
        "business_name": business_name,
        "city": city,
        "state": state,
        "phone": phone,
        "email": email,
        "address": address,
        "contact_name": contact_name,
        "website_url": website_url,
        "business_type": business_type_raw,
        "notes": notes,
    }
    # Strip None values so DB defaults apply cleanly
    row = {k: v for k, v in row.items() if v is not None}

    try:
        result = insert_lead(row)
        lead_id = result.get("lead_id", "—")
        console.print(f"[green]Saved![/green] Lead ID: {lead_id}")
    except Exception as exc:
        console.print(f"[red]Error saving lead:[/red] {exc}")
        raise click.Abort()


if __name__ == "__main__":
    cli()
