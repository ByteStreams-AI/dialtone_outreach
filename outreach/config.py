"""
config.py — centralised settings loaded from .env
"""
import os
from datetime import date, datetime
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# ── Supabase ──────────────────────────────────────────────────────
SUPABASE_URL         = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

# ── AWS SES ───────────────────────────────────────────────────────
AWS_ACCESS_KEY_ID     = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_REGION            = os.getenv("AWS_REGION", "us-east-1")

# ── Sender ────────────────────────────────────────────────────────
FROM_EMAIL = os.environ["FROM_EMAIL"]
FROM_NAME  = os.getenv("FROM_NAME", "Steve Cotton")
FROM_FULL  = f"{FROM_NAME} <{FROM_EMAIL}>"

# ── Sequence timing (days after Email #1 sent_at) ─────────────────
SEQUENCE_DELAYS = {
    1: 0,    # Email #1 — send immediately
    2: 3,    # Email #2 — 3 days later
    3: 7,    # Email #3 — 7 days later
    4: 14,   # Breakup  — 14 days later
    5: 60,   # Re-engage — 60 days after breakup (opener only)
}

# ── Outreach limits ────────────────────────────────────
DAILY_SEND_LIMIT  = int(os.getenv("DAILY_SEND_LIMIT", 20))
SEQUENCE_TIMEZONE = os.getenv("SEQUENCE_TIMEZONE", "America/Chicago")

# ── Warmup ramp (Milestone 2) ────────────────────────────────────
# Optional ISO date (YYYY-MM-DD) for day 1 of the SES warmup. When set,
# ``effective_send_limit()`` returns the limit for the matching day from
# WARMUP_DAY_LIMITS (a comma-separated list). After the schedule is
# exhausted, ``DAILY_SEND_LIMIT`` is used as the steady-state value.
WARMUP_START_DATE = os.getenv("WARMUP_START_DATE", "").strip()
_WARMUP_DAY_LIMITS_RAW = os.getenv("WARMUP_DAY_LIMITS", "5,5,5,10,10,10,20").strip()
try:
    WARMUP_DAY_LIMITS: list[int] = [
        int(part) for part in _WARMUP_DAY_LIMITS_RAW.split(",") if part.strip()
    ]
except ValueError as exc:
    raise ValueError(
        f"WARMUP_DAY_LIMITS must be a comma-separated list of ints, got "
        f"{_WARMUP_DAY_LIMITS_RAW!r}"
    ) from exc


def _parse_warmup_start(value: str) -> Optional[date]:
    """Parse the ``WARMUP_START_DATE`` env var into a ``date``.

    Args:
        value: Raw env string, e.g. ``"2026-05-05"``. Empty string disables
            warmup mode.

    Returns:
        The parsed ``date`` instance or ``None`` when warmup is disabled.

    Raises:
        ValueError: If ``value`` is non-empty but not in ``YYYY-MM-DD``.
    """
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def effective_send_limit(today: Optional[date] = None) -> int:
    """Return the active daily send limit for ``today``.

    Honors the warmup ramp when ``WARMUP_START_DATE`` is set. If ``today``
    is before day 1 of the ramp the function returns 0 so ``run`` exits
    early instead of front-loading sends; once the ramp is exhausted the
    steady-state ``DAILY_SEND_LIMIT`` is used.

    Args:
        today: Optional date override (useful for tests). Defaults to
            ``date.today()`` in local time.

    Returns:
        The effective send limit for the day, in number of emails.
    """
    today = today or date.today()
    start = _parse_warmup_start(WARMUP_START_DATE)
    if start is None:
        return DAILY_SEND_LIMIT
    day_index = (today - start).days  # 0-based index into WARMUP_DAY_LIMITS
    if day_index < 0:
        return 0
    if day_index >= len(WARMUP_DAY_LIMITS):
        return DAILY_SEND_LIMIT
    return WARMUP_DAY_LIMITS[day_index]

# ── Calendly ─────────────────────────────────────────────────────
CALENDLY_URL = os.getenv("CALENDLY_URL", "https://calendly.com/your-link")

# ── CAN-SPAM compliance ──────────────────────────────────────────
# BUSINESS_ADDRESS is the physical postal address required in every
# commercial email (CAN-SPAM Act, 15 U.S.C. § 7704). It must be a real
# mailing address. ``render_email()`` raises if this is unset so we cannot
# accidentally send a non-compliant email.
BUSINESS_ADDRESS    = os.getenv("BUSINESS_ADDRESS", "").strip()
# Legal entity name shown in the footer alongside the address.
COMPANY_LEGAL_NAME  = os.getenv("COMPANY_LEGAL_NAME", "ByteStreams LLC")
# Mailbox that receives unsubscribe requests. Used to compose a mailto:
# link when UNSUBSCRIBE_URL is not set.
UNSUBSCRIBE_EMAIL   = os.getenv("UNSUBSCRIBE_EMAIL", "unsubscribe@dialtone.menu")
# Optional fully-qualified unsubscribe URL (e.g. a Cloudflare Worker).
# When empty, templates fall back to a mailto: link built from
# UNSUBSCRIBE_EMAIL.
UNSUBSCRIBE_URL     = os.getenv("UNSUBSCRIBE_URL", "").strip()

# ── Reply detection (Milestone 3) ─────────────────────────────────
# IMAP credentials for the mailbox that receives replies. The
# ``check-replies`` CLI command connects to this mailbox, scans for
# unread messages from known contacts, and marks them as replied in
# Supabase.  Scheduling (cron / EventBridge) is deferred to M6.
REPLY_CHECK_IMAP_HOST = os.getenv("REPLY_CHECK_IMAP_HOST", "imap.gmail.com")
REPLY_CHECK_IMAP_PORT = int(os.getenv("REPLY_CHECK_IMAP_PORT", "993"))
REPLY_CHECK_EMAIL     = os.getenv("REPLY_CHECK_EMAIL", "").strip()
REPLY_CHECK_PASSWORD  = os.getenv("REPLY_CHECK_PASSWORD", "").strip()

# ── Contact statuses ─────────────────────────────────────────────
class Status:
    NEW           = "new"
    EMAILED_1     = "emailed_1"
    EMAILED_2     = "emailed_2"
    EMAILED_3     = "emailed_3"
    BREAKUP_SENT  = "breakup_sent"
    RE_ENGAGE     = "re_engage"
    DEMO_BOOKED   = "demo_booked"
    PILOT         = "pilot"
    CUSTOMER      = "customer"
    NOT_INTERESTED= "not_interested"
    INVALID       = "invalid"
    REPLIED       = "replied"

# Statuses that should never receive further outreach
TERMINAL_STATUSES = {
    Status.DEMO_BOOKED,
    Status.PILOT,
    Status.CUSTOMER,
    Status.NOT_INTERESTED,
    Status.INVALID,
    Status.REPLIED,
}

# Map sequence number → status after send
SEQUENCE_STATUS_MAP = {
    1: Status.EMAILED_1,
    2: Status.EMAILED_2,
    3: Status.EMAILED_3,
    4: Status.BREAKUP_SENT,
    5: Status.RE_ENGAGE,
}
