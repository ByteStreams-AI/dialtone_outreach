"""preflight.py — Go / no-go checks before a live send.

The :func:`run_preflight` function exercises every external dependency the
runner touches (env vars, Supabase, AWS SES, DNS records for the sending
domain) and prints a Rich table of pass / warn / fail rows. It is the
code-level expression of Milestone 2 steps 1 and 2 in
``docs/project-status.md``.

Usage::

    from outreach.preflight import run_preflight
    exit_code = run_preflight()       # 0 = ok, 1 = blocking failures

Or via the CLI::

    python cli.py preflight
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Iterable, Literal

from rich import box
from rich.console import Console
from rich.table import Table

console = Console()

CheckStatus = Literal["pass", "warn", "fail", "skip"]

# Required env vars that ``outreach.config`` will already raise on. We
# still include them in the report so the operator sees the full picture.
_REQUIRED_ENV_VARS: tuple[str, ...] = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "FROM_EMAIL",
    "BUSINESS_ADDRESS",
)

# Env vars that are optional but recommended before a live cohort.
_RECOMMENDED_ENV_VARS: tuple[str, ...] = (
    "FROM_NAME",
    "COMPANY_LEGAL_NAME",
    "UNSUBSCRIBE_EMAIL",
    "WARMUP_START_DATE",
)


@dataclass
class CheckResult:
    """Outcome of a single preflight check.

    Attributes:
        name: Short label shown in the report.
        status: ``"pass"``, ``"warn"``, ``"fail"``, or ``"skip"``.
        detail: Human-readable description of the result.
    """

    name: str
    status: CheckStatus
    detail: str

    @property
    def is_blocking(self) -> bool:
        """Return ``True`` if this result should fail the preflight gate."""
        return self.status == "fail"


# ── Individual checks ────────────────────────────────────────────


def _check_required_env() -> CheckResult:
    """Verify all hard-required env vars are populated."""
    missing = [name for name in _REQUIRED_ENV_VARS if not os.getenv(name, "").strip()]
    if missing:
        return CheckResult(
            name="env: required vars",
            status="fail",
            detail=f"Missing: {', '.join(missing)}",
        )
    return CheckResult(
        name="env: required vars",
        status="pass",
        detail=f"All {len(_REQUIRED_ENV_VARS)} required vars set",
    )


def _check_recommended_env() -> CheckResult:
    """Warn (not fail) when recommended env vars are unset."""
    missing = [name for name in _RECOMMENDED_ENV_VARS if not os.getenv(name, "").strip()]
    if missing:
        return CheckResult(
            name="env: recommended vars",
            status="warn",
            detail=f"Unset: {', '.join(missing)}",
        )
    return CheckResult(
        name="env: recommended vars",
        status="pass",
        detail="All recommended vars set",
    )


def _check_business_address() -> CheckResult:
    """Confirm BUSINESS_ADDRESS is not the historical placeholder."""
    address = os.getenv("BUSINESS_ADDRESS", "").strip()
    if not address:
        return CheckResult(
            name="env: BUSINESS_ADDRESS",
            status="fail",
            detail="Unset (CAN-SPAM requires a real postal address)",
        )
    if "123 Main St" in address:
        return CheckResult(
            name="env: BUSINESS_ADDRESS",
            status="fail",
            detail="Still set to the placeholder address",
        )
    preview = address.replace("\n", " / ")
    return CheckResult(
        name="env: BUSINESS_ADDRESS",
        status="pass",
        detail=preview[:80],
    )


def _check_supabase() -> CheckResult:
    """Confirm Supabase is reachable and the contacts table is queryable."""
    try:
        from outreach import db

        client = db.get_client()
        client.table("contacts").select("id", count="exact").limit(1).execute()
    except Exception as exc:
        return CheckResult(
            name="supabase: contacts query",
            status="fail",
            detail=str(exc)[:120],
        )
    return CheckResult(
        name="supabase: contacts query",
        status="pass",
        detail="OK",
    )


def _check_ses_quota() -> CheckResult:
    """Surface SES sandbox state and remaining 24-hour budget."""
    try:
        from outreach.email_client import get_send_quota, is_in_sandbox

        quota = get_send_quota()
        sandbox = is_in_sandbox()
    except Exception as exc:
        return CheckResult(
            name="ses: send quota",
            status="fail",
            detail=str(exc)[:120],
        )
    detail = (
        f"max_24h={int(quota['max_24h'])} "
        f"sent={int(quota['sent_last_24h'])} "
        f"remaining={int(quota['remaining'])} "
        f"max_per_sec={quota['max_per_second']}"
    )
    if sandbox:
        return CheckResult(
            name="ses: send quota",
            status="warn",
            detail=f"SANDBOX (verified-recipients only) — {detail}",
        )
    return CheckResult(name="ses: send quota", status="pass", detail=detail)


def _check_ses_identity() -> CheckResult:
    """Confirm FROM_EMAIL is verified for SES sending."""
    try:
        from outreach.config import FROM_EMAIL
        from outreach.email_client import get_ses_client

        ses = get_ses_client()
        resp = ses.get_identity_verification_attributes(Identities=[FROM_EMAIL])
        attrs = resp.get("VerificationAttributes", {}).get(FROM_EMAIL)
    except Exception as exc:
        return CheckResult(
            name="ses: sender identity",
            status="fail",
            detail=str(exc)[:120],
        )
    if not attrs:
        return CheckResult(
            name="ses: sender identity",
            status="fail",
            detail=f"{FROM_EMAIL} is not registered in SES",
        )
    state = attrs.get("VerificationStatus", "Unknown")
    if state == "Success":
        return CheckResult(
            name="ses: sender identity",
            status="pass",
            detail=f"{FROM_EMAIL} verified",
        )
    return CheckResult(
        name="ses: sender identity",
        status="fail",
        detail=f"{FROM_EMAIL} state={state}",
    )


def _check_ses_dkim() -> CheckResult:
    """Check DKIM is enabled + verified for the sender domain."""
    try:
        from outreach.config import FROM_EMAIL
        from outreach.email_client import get_ses_client

        domain = FROM_EMAIL.split("@", 1)[1]
        ses = get_ses_client()
        resp = ses.get_identity_dkim_attributes(Identities=[domain])
        attrs = resp.get("DkimAttributes", {}).get(domain)
    except Exception as exc:
        return CheckResult(
            name="ses: dkim",
            status="warn",
            detail=str(exc)[:120],
        )
    if not attrs:
        return CheckResult(
            name="ses: dkim",
            status="warn",
            detail=f"{domain} not registered as a DKIM identity",
        )
    enabled = attrs.get("DkimEnabled", False)
    state = attrs.get("DkimVerificationStatus", "Unknown")
    if enabled and state == "Success":
        return CheckResult(
            name="ses: dkim",
            status="pass",
            detail=f"{domain} DKIM enabled + verified",
        )
    return CheckResult(
        name="ses: dkim",
        status="fail",
        detail=f"{domain} dkim_enabled={enabled} state={state}",
    )


def _check_dns_records() -> Iterable[CheckResult]:
    """Look up SPF + DMARC TXT records for the sender domain.

    Yields one :class:`CheckResult` per record. ``dnspython`` is optional;
    if it isn't installed both checks return ``"skip"`` so the operator can
    fall back to ``dig`` manually.
    """
    try:
        from outreach.config import FROM_EMAIL

        domain = FROM_EMAIL.split("@", 1)[1]
    except Exception as exc:
        yield CheckResult(name="dns: spf", status="fail", detail=str(exc)[:120])
        yield CheckResult(name="dns: dmarc", status="fail", detail=str(exc)[:120])
        return

    try:
        import dns.resolver  # type: ignore[import-not-found]
    except ImportError:
        skip_detail = "dnspython not installed; run `dig TXT <domain>` manually"
        yield CheckResult(name="dns: spf", status="skip", detail=skip_detail)
        yield CheckResult(name="dns: dmarc", status="skip", detail=skip_detail)
        return

    yield _query_txt_record(
        label="dns: spf",
        domain=domain,
        match=lambda value: value.lower().startswith("v=spf1"),
    )
    yield _query_txt_record(
        label="dns: dmarc",
        domain=f"_dmarc.{domain}",
        match=lambda value: value.lower().startswith("v=dmarc1"),
    )


def _query_txt_record(
    *, label: str, domain: str, match: Callable[[str], bool]
) -> CheckResult:
    """Resolve TXT records for ``domain`` and report whether one matches."""
    import dns.resolver  # type: ignore[import-not-found]

    try:
        answer = dns.resolver.resolve(domain, "TXT", lifetime=5.0)
    except Exception as exc:
        return CheckResult(label, status="fail", detail=f"{domain}: {exc}")
    for record in answer:
        text = b"".join(record.strings).decode("utf-8", errors="replace")
        if match(text):
            return CheckResult(label, status="pass", detail=text[:120])
    return CheckResult(
        label,
        status="fail",
        detail=f"{domain}: no matching TXT record",
    )


# ── Orchestration ────────────────────────────────────────────────


_CHECKS: tuple[Callable[[], CheckResult], ...] = (
    _check_required_env,
    _check_recommended_env,
    _check_business_address,
    _check_supabase,
    _check_ses_quota,
    _check_ses_identity,
    _check_ses_dkim,
)


def run_preflight() -> int:
    """Run every preflight check and print a Rich summary table.

    Returns:
        ``0`` if all checks passed (warnings allowed), ``1`` if any check
        returned ``"fail"``. Suitable for ``sys.exit()``.
    """
    # ``outreach.config`` calls ``load_dotenv()`` at import time, but the
    # env-vars / business-address checks below run *before* anything
    # imports it. Trigger dotenv loading explicitly so those checks see
    # what's in ``.env`` rather than an empty environment.
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:  # pragma: no cover - defensive
        pass

    results: list[CheckResult] = []
    for check in _CHECKS:
        try:
            results.append(check())
        except Exception as exc:  # pragma: no cover - defensive
            results.append(
                CheckResult(name=check.__name__, status="fail", detail=str(exc)[:120])
            )
    results.extend(list(_check_dns_records()))

    table = Table(
        title="DialTone Outreach — Preflight",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold blue",
    )
    table.add_column("Check", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Detail", style="white", overflow="fold")

    style_for = {
        "pass": "green",
        "warn": "yellow",
        "fail": "red",
        "skip": "dim",
    }
    glyph_for = {"pass": "✓", "warn": "!", "fail": "✗", "skip": "·"}

    for result in results:
        table.add_row(
            result.name,
            f"[{style_for[result.status]}]{glyph_for[result.status]} "
            f"{result.status.upper()}[/{style_for[result.status]}]",
            result.detail,
        )

    console.print(table)

    failures = [r for r in results if r.is_blocking]
    warns = [r for r in results if r.status == "warn"]
    if failures:
        console.print(
            f"\n[red]Preflight FAILED[/red] — {len(failures)} blocking issue(s)."
        )
        return 1
    if warns:
        console.print(
            f"\n[yellow]Preflight passed with {len(warns)} warning(s).[/yellow]"
        )
    else:
        console.print("\n[green]Preflight passed.[/green]")
    return 0
