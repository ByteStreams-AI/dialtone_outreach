"""
scripts/import_contacts.py
--------------------------
Import contacts from Outscraper or Apollo CSV exports into Supabase.

Usage:
    python scripts/import_contacts.py --source outscraper --file export.csv
    python scripts/import_contacts.py --source apollo     --file export.csv
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import click
import pandas as pd
from rich.console import Console
from rich.progress import track
from outreach.db import get_client, upsert_contact

console = Console()

# ── Column mappings ───────────────────────────────────────────────

OUTSCRAPER_MAP = {
    "name":          "restaurant_name",
    "phone":         "business_phone",
    "site":          "website",
    "email":         "restaurant_email",
    "rating":        "rating",
    "reviews":       "reviews",
    "category":      "category",
    "full_address":  "address",
    "city":          "city",
    "state":         "state",
    "postal_code":   "zip",
}

APOLLO_MAP = {
    "first name":        "owner_first",
    "last name":         "owner_last",
    "title":             "title",
    "email":             "owner_email",
    "direct phone":      "owner_phone",
    "company":           "restaurant_name",
    "website":           "website",
    "city":              "city",
    "state":             "state",
}

KNOWN_CHAINS = [
    "mcdonald","subway","chick-fil","wendy","burger king","starbucks",
    "chipotle","applebee","chili's","olive garden","ihop","denny",
    "waffle house","taco bell","pizza hut","domino","kfc","popeyes",
    "panera","cracker barrel","sonic","dairy queen","little caesars",
]


def extract_domain(value: str) -> str:
    if not value or pd.isna(value):
        return ""
    v = str(value).lower().strip()
    for prefix in ["https://", "http://", "www."]:
        v = v.replace(prefix, "")
    return v.split("/")[0].strip()


def is_chain(name: str) -> bool:
    if not name:
        return False
    n = name.lower()
    return any(chain in n for chain in KNOWN_CHAINS)


def passes_quality_filter(row: pd.Series, source: str) -> tuple[bool, str]:
    """Returns (passes, reason_if_not)."""
    if source == "outscraper":
        rating  = row.get("rating")
        reviews = row.get("reviews")
        name    = row.get("restaurant_name", "")

        try:
            rating = float(rating)
        except (TypeError, ValueError):
            return False, "invalid rating"

        try:
            reviews = int(reviews)
        except (TypeError, ValueError):
            return False, "invalid review count"

        if not (3.5 <= rating <= 4.5):
            return False, f"rating {rating} out of range"
        if not (50 <= reviews <= 800):
            return False, f"review count {reviews} out of range"
        if is_chain(name):
            return False, "chain restaurant"

    if source == "apollo":
        email = row.get("owner_email", "")
        if not email or pd.isna(email):
            return False, "no email"

    return True, ""


def process_outscraper(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.lower().strip() for c in df.columns]
    df = df.rename(columns={k: v for k, v in OUTSCRAPER_MAP.items() if k in df.columns})
    df["domain"] = df.get("website", pd.Series(dtype=str)).apply(extract_domain)
    df["source"] = "outscraper"
    df["status"] = "new"
    return df


def process_apollo(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.lower().strip() for c in df.columns]
    df = df.rename(columns={k: v for k, v in APOLLO_MAP.items() if k in df.columns})
    df["domain"] = df.get("website", pd.Series(dtype=str)).apply(extract_domain)

    # Also try deriving domain from email if website missing
    mask = df["domain"] == ""
    if "owner_email" in df.columns:
        df.loc[mask, "domain"] = df.loc[mask, "owner_email"].apply(
            lambda e: e.split("@")[1] if "@" in str(e) else ""
        )

    df["source"] = "apollo"
    df["status"] = "new"
    return df


@click.command()
@click.option("--source", required=True,
              type=click.Choice(["outscraper", "apollo"], case_sensitive=False),
              help="Source of the CSV file")
@click.option("--file",   required=True,
              type=click.Path(exists=True), help="Path to CSV file")
@click.option("--dry-run", is_flag=True, default=False,
              help="Preview import without writing to Supabase")
def main(source, file, dry_run):
    console.print(f"\n[bold blue]DialTone Contact Importer[/bold blue]")
    console.print(f"Source: [cyan]{source}[/cyan]  File: [cyan]{file}[/cyan]  "
                  f"{'[yellow]DRY RUN[/yellow]' if dry_run else '[green]LIVE[/green]'}\n")

    df = pd.read_csv(file, dtype=str, low_memory=False)
    console.print(f"Loaded [bold]{len(df)}[/bold] rows from CSV.\n")

    if source == "outscraper":
        df = process_outscraper(df)
    else:
        df = process_apollo(df)

    # Deduplicate within this file by domain
    df = df.drop_duplicates(subset=["domain"], keep="first")

    imported = skipped = errors = 0

    if not dry_run:
        client = get_client()

    for _, row in track(df.iterrows(), total=len(df), description="Importing..."):
        record = {k: (None if pd.isna(v) else v)
                  for k, v in row.to_dict().items()}

        # Skip rows with no domain
        if not record.get("domain"):
            skipped += 1
            continue

        passes, reason = passes_quality_filter(row, source)
        if not passes:
            skipped += 1
            continue

        if dry_run:
            console.print(
                f"  [dim]→[/dim] [cyan]{record.get('restaurant_name','?')}[/cyan]  "
                f"domain={record.get('domain')}  "
                f"email={record.get('owner_email','—')}"
            )
            imported += 1
            continue

        try:
            upsert_contact(client, record)
            imported += 1
        except Exception as e:
            console.print(f"  [red]✗[/red] {record.get('domain')}: {e}")
            errors += 1

    console.print(f"\n[bold]Import complete.[/bold]")
    console.print(f"  Imported: [green]{imported}[/green]")
    console.print(f"  Skipped:  [yellow]{skipped}[/yellow]")
    console.print(f"  Errors:   [red]{errors}[/red]\n")


if __name__ == "__main__":
    main()
