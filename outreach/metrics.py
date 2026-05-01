"""metrics.py — Aggregate send-quality metrics for the live cohort.

Used to evaluate Milestone 2 acceptance criteria after a cohort runs:
bounce rate < 5%, complaint rate < 0.1%, and at least one real reply.

Two report shapes are supported:

* time-window: ``report_window(since="7d")`` — every email sent in the
  last N days
* cohort: ``report_cohort(name="batch-1")`` — every email sent to the
  contacts in a locked cohort (regardless of send date)

Both shapes return the same :class:`MetricsReport` dataclass, which is
also rendered as a Rich table for CLI use via :func:`print_report`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from rich import box
from rich.console import Console
from rich.table import Table

from outreach import db
from outreach.config import Status

console = Console()

_SINCE_RE = re.compile(r"^\s*(\d+)\s*([dhm])\s*$", re.IGNORECASE)


@dataclass
class MetricsReport:
    """Aggregated metrics for a cohort or time window.

    Attributes:
        scope: Human-readable label for the report subject (e.g.
            ``"last 7d"`` or ``"cohort: batch-1"``).
        since_iso: ISO-8601 lower-bound for ``sent_at``, or ``None`` for
            cohort reports.
        sent: Number of emails sent in scope.
        opened: Number with a non-null ``opened_at``.
        replied: Number with a non-null ``replied_at``.
        bounced: Number with a non-null ``bounced_at``.
        complained: Number with a non-null ``complained_at``.
        demos_booked: Status-derived count from ``contacts``.
    """

    scope: str
    since_iso: Optional[str]
    sent: int
    opened: int
    replied: int
    bounced: int
    complained: int
    demos_booked: int

    @property
    def bounce_rate(self) -> float:
        """Bounce rate as a fraction of ``sent``."""
        return self.bounced / self.sent if self.sent else 0.0

    @property
    def complaint_rate(self) -> float:
        """Complaint rate as a fraction of ``sent``."""
        return self.complained / self.sent if self.sent else 0.0

    @property
    def reply_rate(self) -> float:
        """Reply rate as a fraction of ``sent``."""
        return self.replied / self.sent if self.sent else 0.0

    @property
    def open_rate(self) -> float:
        """Open rate as a fraction of ``sent`` (best-effort, not all\n        clients pixel-track)."""
        return self.opened / self.sent if self.sent else 0.0


def parse_since(value: str) -> str:
    """Convert ``"7d"`` / ``"24h"`` / ``"30m"`` into an ISO timestamp.

    Args:
        value: Duration string. Supported units: ``d`` (days), ``h``
            (hours), ``m`` (minutes).

    Returns:
        An ISO-8601 UTC timestamp ``N`` units before now.

    Raises:
        ValueError: If ``value`` is not in the supported format.
    """
    match = _SINCE_RE.match(value)
    if not match:
        raise ValueError(
            f"--since must be like '7d', '24h', or '30m' (got {value!r})"
        )
    amount = int(match.group(1))
    unit = match.group(2).lower()
    delta = {
        "d": timedelta(days=amount),
        "h": timedelta(hours=amount),
        "m": timedelta(minutes=amount),
    }[unit]
    return (datetime.now(timezone.utc) - delta).isoformat()


def _demos_booked(client) -> int:
    """Return the number of contacts currently in ``demo_booked``."""
    counts = db.get_status_counts(client)
    return counts.get(Status.DEMO_BOOKED, 0)


def report_window(since: str) -> MetricsReport:
    """Build a :class:`MetricsReport` for emails sent in a time window.

    Args:
        since: Duration string accepted by :func:`parse_since`.

    Returns:
        The aggregated report.
    """
    client = db.get_client()
    since_iso = parse_since(since)
    counters = db.get_email_log_metrics(client, since_iso=since_iso)
    return MetricsReport(
        scope=f"last {since}",
        since_iso=since_iso,
        sent=counters["sent"],
        opened=counters["opened"],
        replied=counters["replied"],
        bounced=counters["bounced"],
        complained=counters["complained"],
        demos_booked=_demos_booked(client),
    )


def report_cohort(name: str) -> MetricsReport:
    """Build a :class:`MetricsReport` scoped to a locked cohort.

    Args:
        name: Cohort identifier; resolved through
            :func:`outreach.cohort.load_cohort`.

    Returns:
        The aggregated report.
    """
    from outreach.cohort import load_cohort

    cohort = load_cohort(name)
    client = db.get_client()
    counters = db.get_email_log_metrics(client, contact_ids=cohort.contact_ids)
    return MetricsReport(
        scope=f"cohort: {cohort.name} ({len(cohort.contact_ids)} contacts)",
        since_iso=None,
        sent=counters["sent"],
        opened=counters["opened"],
        replied=counters["replied"],
        bounced=counters["bounced"],
        complained=counters["complained"],
        demos_booked=_demos_booked(client),
    )


def _rate_cell(rate: float, threshold: float, *, lower_is_better: bool) -> str:
    """Render a percentage with red/yellow/green colouring vs threshold."""
    pct = f"{rate * 100:.2f}%"
    if lower_is_better:
        if rate <= threshold:
            return f"[green]{pct}[/green]"
        if rate <= threshold * 2:
            return f"[yellow]{pct}[/yellow]"
        return f"[red]{pct}[/red]"
    if rate >= threshold:
        return f"[green]{pct}[/green]"
    return f"[yellow]{pct}[/yellow]"


def print_report(report: MetricsReport) -> None:
    """Render ``report`` as a Rich table and write it to stdout."""
    table = Table(
        title=f"DialTone Outreach — Metrics ({report.scope})",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold blue",
    )
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", justify="right")
    table.add_column("Notes", style="white", overflow="fold")

    table.add_row("Sent", str(report.sent), "Emails dispatched in scope")
    table.add_row("Opened", str(report.opened), f"{report.open_rate * 100:.1f}% open rate")
    table.add_row(
        "Replied",
        str(report.replied),
        f"{report.reply_rate * 100:.2f}% reply rate (M2 needs ≥1)",
    )
    table.add_row(
        "Bounced",
        str(report.bounced),
        f"{_rate_cell(report.bounce_rate, 0.05, lower_is_better=True)} (M2 target < 5%)",
    )
    table.add_row(
        "Complained",
        str(report.complained),
        f"{_rate_cell(report.complaint_rate, 0.001, lower_is_better=True)} (M2 target < 0.1%)",
    )
    table.add_row(
        "Demos booked",
        str(report.demos_booked),
        "Status-derived (all-time, not scope-filtered)",
    )

    console.print(table)

    if report.sent == 0:
        console.print(
            "[yellow]No emails in scope yet — run a cohort first.[/yellow]"
        )
        return

    failures: list[str] = []
    if report.bounce_rate >= 0.05:
        failures.append(
            f"bounce rate {report.bounce_rate * 100:.2f}% ≥ 5%"
        )
    if report.complaint_rate >= 0.001:
        failures.append(
            f"complaint rate {report.complaint_rate * 100:.2f}% ≥ 0.1%"
        )
    if failures:
        console.print(
            "[red]M2 acceptance failing:[/red] " + "; ".join(failures)
        )
    elif report.replied >= 1:
        console.print(
            "[green]M2 acceptance criteria met for this scope.[/green]"
        )
    else:
        console.print(
            "[yellow]Bounce/complaint within thresholds; "
            "still waiting on the first reply for M2 acceptance.[/yellow]"
        )
