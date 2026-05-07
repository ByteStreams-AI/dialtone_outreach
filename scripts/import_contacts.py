"""
scripts/import_contacts.py
--------------------------
Import contacts from a CSV export into Supabase.

The importer is source-agnostic: it normalises the incoming columns into a
canonical schema (see ``REQUIRED_FIELDS`` / ``CONTACT_COLUMNS``) and then
upserts each row keyed on ``domain``. Source-specific column-name mappings
live in ``SOURCE_MAPS`` — add a new entry there to support a new vendor.

Usage:
    python scripts/import_contacts.py --source apollo --file export.csv
    python scripts/import_contacts.py --source manual --file canonical.csv
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import click
import pandas as pd
from rich.console import Console
from rich.progress import track

from outreach.db import get_client, upsert_contact
from outreach.sources import SOURCE_MAPS
from outreach.templates import clean_company_name

console = Console()

# ── Canonical input contract ──────────────────────────────────────

# Hard requirements: every imported row must populate these fields. Rows
# missing either are skipped with a clear reason.
REQUIRED_FIELDS: frozenset[str] = frozenset({"domain", "owner_email"})

# All columns that exist on the ``contacts`` table in ``schema.sql``. The
# upsert loop filters every record through this set so vendor-specific
# extras (Apollo's ``# Employees``, ``Industry``, ``Annual Revenue``, etc.)
# are dropped before PostgREST sees them. Keep this aligned with
# ``schema.sql`` — adding a column there without adding it here means the
# value will be silently dropped during import.
CONTACT_COLUMNS: frozenset[str] = frozenset({
    "restaurant_name",
    "business_phone",
    "website",
    "restaurant_email",
    "domain",
    "address",
    "city",
    "state",
    "zip",
    "owner_first",
    "owner_last",
    "owner_email",
    "owner_phone",
    "title",
    "status",
    "lead_score",
    "notes",
    "source",
})

# Source-specific column mappings live in ``outreach.sources`` so the
# top-level CLI can validate ``--source`` choices without pulling pandas /
# Supabase imports at module load.


# ── Helpers ───────────────────────────────────────────────────────


def extract_domain(value: str) -> str:
    if not value or pd.isna(value):
        return ""
    v = str(value).lower().strip()
    for prefix in ["https://", "http://", "www."]:
        v = v.replace(prefix, "")
    return v.split("/")[0].strip()


def passes_quality_filter(row: pd.Series, source: str) -> tuple[bool, str]:
    """Source-specific deliverability checks layered on top of the contract.

    Returns:
        ``(passes, reason)`` — when ``passes`` is False, ``reason`` carries
        a one-line explanation suitable for an operator log line.
    """
    if source == "apollo":
        # Apollo provides an "email status" column populated by
        # ZeroBounce / their own verifier. Only allow rows that came
        # back "valid" — anything else (catch-all, risky, etc.) is a
        # deliverability liability.
        email_status = (row.get("email status") or "").strip().lower()
        if email_status and email_status != "valid":
            return False, f"email status={email_status}"

    return True, ""


def process(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Normalize a CSV export into the canonical contacts schema.

    Args:
        df: Raw CSV loaded with ``pd.read_csv``.
        source: Source key matching a ``SOURCE_MAPS`` entry.

    Returns:
        A normalized DataFrame ready for the upsert loop.
    """
    column_map = SOURCE_MAPS[source]

    df.columns = [c.lower().strip() for c in df.columns]
    if column_map:
        df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

    df["domain"] = df.get("website", pd.Series(dtype=str)).apply(extract_domain)

    # Fall back to deriving domain from email when website is missing.
    mask = df["domain"] == ""
    if "owner_email" in df.columns:
        df.loc[mask, "domain"] = df.loc[mask, "owner_email"].apply(
            lambda e: e.split("@")[1] if "@" in str(e) else ""
        )

    # Strip LLC / Inc. / quotes from the restaurant name once at import
    # time so the database stores the cleaned value forever.
    if "restaurant_name" in df.columns:
        df["restaurant_name"] = df["restaurant_name"].apply(
            lambda v: clean_company_name(v) if pd.notna(v) else v
        )

    df["source"] = source
    df["status"] = "new"
    return df


def _missing_required(record: dict) -> list[str]:
    """Return the list of required fields absent from ``record``."""
    return [
        f for f in REQUIRED_FIELDS
        if not record.get(f) or str(record[f]).strip() == ""
    ]


@click.command()
@click.option("--source", default="apollo", show_default=True,
              type=click.Choice(sorted(SOURCE_MAPS.keys()), case_sensitive=False),
              help="Source of the CSV file. Use 'manual' for canonical-schema CSVs.")
@click.option("--file",   required=True,
              type=click.Path(exists=True), help="Path to CSV file")
@click.option("--dry-run", is_flag=True, default=False,
              help="Preview import without writing to Supabase")
def main(source, file, dry_run):
    console.print("\n[bold blue]DialTone Contact Importer[/bold blue]")
    console.print(f"Source: [cyan]{source}[/cyan]  File: [cyan]{file}[/cyan]  "
                  f"{'[yellow]DRY RUN[/yellow]' if dry_run else '[green]LIVE[/green]'}\n")

    df = pd.read_csv(file, dtype=str, low_memory=False)
    console.print(f"Loaded [bold]{len(df)}[/bold] rows from CSV.\n")

    df = process(df, source)

    # Deduplicate within this file by domain
    df = df.drop_duplicates(subset=["domain"], keep="first")

    imported = skipped = errors = 0

    if not dry_run:
        client = get_client()

    for _, row in track(df.iterrows(), total=len(df), description="Importing..."):
        # Filter the record to columns that actually exist on the
        # ``contacts`` table; otherwise vendor-specific extras would be
        # sent to PostgREST and rejected with a schema-cache error.
        record = {
            k: (None if pd.isna(v) else v)
            for k, v in row.to_dict().items()
            if k in CONTACT_COLUMNS
        }

        missing = _missing_required(record)
        if missing:
            console.print(
                f"  [dim]skip[/dim] domain={record.get('domain') or '?'}  "
                f"missing={sorted(missing)}"
            )
            skipped += 1
            continue

        passes, reason = passes_quality_filter(row, source)
        if not passes:
            console.print(
                f"  [dim]skip[/dim] domain={record.get('domain') or '?'}  "
                f"reason={reason}"
            )
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

    console.print("\n[bold]Import complete.[/bold]")
    console.print(f"  Imported: [green]{imported}[/green]")
    console.print(f"  Skipped:  [yellow]{skipped}[/yellow]")
    console.print(f"  Errors:   [red]{errors}[/red]\n")


if __name__ == "__main__":
    main()
