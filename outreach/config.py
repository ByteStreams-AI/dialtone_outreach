"""
config.py — centralised settings loaded from .env
"""
import os
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

# ── Outreach limits ───────────────────────────────────────────────
DAILY_SEND_LIMIT  = int(os.getenv("DAILY_SEND_LIMIT", 20))
SEQUENCE_TIMEZONE = os.getenv("SEQUENCE_TIMEZONE", "America/Chicago")

# ── Calendly ─────────────────────────────────────────────────────
CALENDLY_URL = os.getenv("CALENDLY_URL", "https://calendly.com/your-link")

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
