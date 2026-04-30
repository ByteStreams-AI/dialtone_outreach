"""scripts/preview_templates.py
=================================

Render all 5 outreach templates against 5 real Apollo contacts and write
the output to ``developer/template-previews/`` so the project owner can
visually review HTML and plain-text variants before unfreezing the live
send (project-status.md milestone 1, step 6).

The script also acts as a regression smoke check: if any rendered output
still contains a Jinja-style ``{{ ... }}`` artifact (e.g. the
unsubscribe-link bug from milestone 1) the script exits with a non-zero
status and prints the offending file.

Usage::

    python scripts/preview_templates.py
    python scripts/preview_templates.py --csv path/to/apollo.csv --count 5
"""
from __future__ import annotations

import os
import re
import sys

# Allow running as ``python scripts/preview_templates.py`` from the
# repository root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from typing import Iterable

import click
import pandas as pd
from rich.console import Console

from outreach.templates import TEMPLATES, render_email
from scripts.import_contacts import process_apollo

console = Console()

DEFAULT_CSV = Path(__file__).resolve().parent.parent / "docs" / "apollo-contacts-export.csv"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "developer" / "template-previews"

# Catches both opening and closing Jinja delimiters, with or without
# whitespace, so we don't miss a regression of the brace-leak bug.
_JINJA_ARTIFACT_RE = re.compile(r"\{\{\s*\w+|\}\}")


def _slug(value: str) -> str:
    """Return a filesystem-safe slug for a contact identifier."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value or "").strip("-").lower()
    return cleaned or "contact"


def _pick_samples(df: pd.DataFrame, count: int) -> list[dict]:
    """Pick up to ``count`` Apollo rows that have both an email and name.

    Args:
        df: DataFrame produced by ``process_apollo``.
        count: Maximum number of sample contacts to return.

    Returns:
        A list of dicts shaped like the contacts table rows.
    """
    samples: list[dict] = []
    for _, row in df.iterrows():
        if len(samples) >= count:
            break
        record = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
        if not record.get("owner_email") or not record.get("restaurant_name"):
            continue
        samples.append(record)
    return samples


def _scan_artifacts(content: str) -> list[str]:
    """Return any Jinja-like artifacts found in rendered output."""
    return _JINJA_ARTIFACT_RE.findall(content)


def _write_preview(out_dir: Path, contact: dict, seq_num: int,
                   rendered: dict) -> tuple[Path, Path]:
    """Write the rendered text + html previews to disk.

    Args:
        out_dir: Destination directory.
        contact: Sample contact row.
        seq_num: Sequence number being rendered (1-5).
        rendered: Output of ``render_email``.

    Returns:
        Tuple of ``(text_path, html_path)``.
    """
    base = f"{_slug(contact.get('domain') or contact.get('owner_email'))}-seq{seq_num}"
    txt_path = out_dir / f"{base}.txt"
    html_path = out_dir / f"{base}.html"
    txt_path.write_text(
        f"Subject: {rendered['subject']}\n\n{rendered['text']}",
        encoding="utf-8",
    )
    html_path.write_text(rendered["html"], encoding="utf-8")
    return txt_path, html_path


def render_previews(csv_path: Path, out_dir: Path, count: int) -> int:
    """Render preview emails and write them under ``out_dir``.

    Args:
        csv_path: Apollo CSV export to sample from.
        out_dir: Directory to write the rendered previews into. Created
            if it doesn't exist.
        count: Number of sample contacts to render against.

    Returns:
        Process exit code: 0 on success, 1 if any rendered file still
        contains a ``{{ ... }}`` artifact.
    """
    if not csv_path.exists():
        console.print(f"[red]CSV not found:[/red] {csv_path}")
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(csv_path, dtype=str, low_memory=False)
    df = process_apollo(raw)
    samples = _pick_samples(df, count)
    if not samples:
        console.print("[red]No usable Apollo rows found in CSV.[/red]")
        return 2

    console.print(
        f"\n[bold blue]Template Preview[/bold blue]  "
        f"contacts=[bold]{len(samples)}[/bold]  "
        f"templates=[bold]{len(TEMPLATES)}[/bold]  "
        f"out=[dim]{out_dir}[/dim]\n"
    )

    artifacts: list[tuple[Path, list[str]]] = []
    for contact in samples:
        console.print(
            f"[cyan]{contact.get('restaurant_name')}[/cyan]  "
            f"<{contact.get('owner_email')}>  "
            f"[dim]{contact.get('city') or '—'}[/dim]"
        )
        for seq_num in TEMPLATES:
            rendered = render_email(
                sequence_number = seq_num,
                first_name      = contact.get("owner_first", ""),
                restaurant_name = contact.get("restaurant_name", ""),
                city            = contact.get("city", ""),
                to_email        = contact.get("owner_email"),
            )
            txt_path, html_path = _write_preview(out_dir, contact, seq_num, rendered)
            for path in (txt_path, html_path):
                hits = _scan_artifacts(path.read_text(encoding="utf-8"))
                if hits:
                    artifacts.append((path, hits))
            console.print(
                f"  seq=[bold]{seq_num}[/bold]  "
                f"subject=[white]{rendered['subject']}[/white]"
            )
        console.print("")

    if artifacts:
        console.print("[red]Found unrendered Jinja artifacts:[/red]")
        for path, hits in artifacts:
            console.print(f"  {path}: {hits[:5]}")
        return 1

    console.print(
        f"[green]\u2713[/green] {len(samples) * len(TEMPLATES)} previews written, "
        f"no template artifacts detected.\n"
        f"Open the HTML files in Gmail / Apple Mail for visual review."
    )
    return 0


@click.command()
@click.option(
    "--csv",
    "csv_path",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=DEFAULT_CSV,
    show_default=True,
    help="Apollo CSV to sample contacts from.",
)
@click.option(
    "--out",
    "out_dir",
    type=click.Path(path_type=Path, file_okay=False),
    default=DEFAULT_OUT,
    show_default=True,
    help="Directory to write rendered previews into.",
)
@click.option(
    "--count",
    type=click.IntRange(min=1, max=50),
    default=5,
    show_default=True,
    help="Number of sample contacts to render against.",
)
def main(csv_path: Path, out_dir: Path, count: int) -> None:
    """CLI entry point for ``python scripts/preview_templates.py``."""
    sys.exit(render_previews(csv_path, out_dir, count))


if __name__ == "__main__":
    main()
