"""templates.py — All outreach email templates with personalisation tokens.

Each template function returns a dict::

    {"subject": str, "text": str, "html": str}

Available tokens (passed as kwargs to ``render_email``):

* ``first_name``       — owner first name (or ``"there"`` as fallback)
* ``restaurant_name``  — restaurant name (cleaned of LLC/Inc./quotes)
* ``city``             — city the restaurant is located in
* ``calendly_url``     — booking link
* ``from_name``        — sender display name

The module also enforces CAN-SPAM compliance: every rendered email
includes the configured ``BUSINESS_ADDRESS``, a sender identity line,
and a working unsubscribe link in both the HTML and plain-text bodies.
"""
from __future__ import annotations

import re
from html import escape as html_escape
from urllib.parse import quote

from jinja2 import Template

from outreach.config import (
    BUSINESS_ADDRESS,
    CALENDLY_URL,
    COMPANY_LEGAL_NAME,
    FROM_NAME,
    UNSUBSCRIBE_EMAIL,
    UNSUBSCRIBE_URL,
)


# ── Helpers ───────────────────────────────────────────────────────


def _render(tmpl: str, **kwargs) -> str:
    """Render a Jinja2 template string with the given context."""
    return Template(tmpl).render(**kwargs)


# Trailing legal suffixes / corporate forms that should be stripped from
# Apollo's "Company Name" before it's used as a friendly restaurant name.
_COMPANY_SUFFIX_RE = re.compile(
    r"""
    [\s,]*                  # optional leading separator
    \b(
        l\.?\s*l\.?\s*c\.?  # LLC, L.L.C., L L C
        | inc\.?            # Inc, Inc.
        | incorporated
        | corp\.?
        | corporation
        | co\.?             # Co, Co.
        | ltd\.?
        | limited
        | l\.?p\.?          # LP, L.P.
        | p\.?l\.?l\.?c\.?  # PLLC
        | p\.?c\.?          # PC
    )\b
    [\s.,]*$                # eat trailing whitespace/punctuation
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Quote characters that occasionally surround Apollo company names.
_QUOTE_CHARS = "\"'\u201c\u201d\u2018\u2019`"


def clean_company_name(name: str) -> str:
    """Normalize an Apollo "Company Name" into a friendly outreach name.

    Strips trailing corporate suffixes (``LLC``, ``Inc.``, ``Corp.``,
    ``Ltd.``, ``Co.``, ``PLLC``, ``PC``, ``L.P.``), surrounding quote
    characters, and collapses internal whitespace.

    Args:
        name: Raw company name as it appears in the imported CSV.

    Returns:
        Cleaned company name. Returns an empty string if ``name`` is
        falsy or becomes empty after stripping.
    """
    if not name:
        return ""

    cleaned = str(name).strip().strip(_QUOTE_CHARS).strip()
    # Strip suffixes repeatedly so "Foo Bar Inc, LLC" collapses cleanly.
    while True:
        new = _COMPANY_SUFFIX_RE.sub("", cleaned).strip().strip(_QUOTE_CHARS).strip()
        if new == cleaned:
            break
        cleaned = new
    cleaned = re.sub(r"\s+", " ", cleaned).strip(",.; ").strip()
    return cleaned


def _resolve_unsubscribe_url(to_email: str | None = None) -> str:
    """Return a valid unsubscribe link.

    Prefers ``UNSUBSCRIBE_URL`` when configured; otherwise composes a
    ``mailto:`` link from ``UNSUBSCRIBE_EMAIL`` with a pre-filled subject
    that lets recipients unsubscribe with a single click.

    Args:
        to_email: Optional recipient address; included in the subject so
            the unsubscribe handler can identify the sender quickly.

    Returns:
        An absolute URL safe to drop into an HTML ``href``.
    """
    if UNSUBSCRIBE_URL:
        return UNSUBSCRIBE_URL
    subject = "Unsubscribe"
    if to_email:
        subject = f"Unsubscribe {to_email}"
    return f"mailto:{UNSUBSCRIBE_EMAIL}?subject={quote(subject)}"


def _format_address_html(address: str) -> str:
    """Render a possibly multi-line postal address as HTML."""
    parts = [p.strip() for p in re.split(r"\r?\n", address) if p.strip()]
    return "<br/>".join(parts)


def _format_address_text(address: str) -> str:
    """Render a possibly multi-line postal address as plain text."""
    parts = [p.strip() for p in re.split(r"\r?\n", address) if p.strip()]
    return "\n".join(parts)


def _text_footer(*, unsubscribe_url: str, business_address: str,
                 company_legal_name: str, sender_name: str) -> str:
    """Build the CAN-SPAM compliant plain-text footer.

    Args:
        unsubscribe_url: Resolved unsubscribe link.
        business_address: Real postal address for the sending entity.
        company_legal_name: Legal entity name shown next to the address.
        sender_name: Display name of the human sender.

    Returns:
        A footer string starting with a leading separator.
    """
    return (
        "\n\n--\n"
        f"{sender_name} on behalf of {company_legal_name}\n"
        f"{_format_address_text(business_address)}\n\n"
        f"To stop receiving these emails, reply with \"unsubscribe\" or "
        f"visit:\n{unsubscribe_url}\n"
    )


def _html_wrap(text: str, *, unsubscribe_url: str, business_address: str,
               company_legal_name: str, sender_name: str) -> str:
    """Wrap a plain-text email body in CAN-SPAM compliant HTML.

    Args:
        text: Already-Jinja-rendered plain text body (without the text
            footer; the HTML footer is appended here instead).
        unsubscribe_url: Resolved unsubscribe link.
        business_address: Real postal address for the sending entity.
        company_legal_name: Legal entity name shown next to the address.
        sender_name: Display name of the human sender.

    Returns:
        A complete HTML document suitable for the SES ``Body.Html`` field.
    """
    # html.escape() ensures personalisation tokens that contain HTML
    # special chars (e.g. "Bob & Carol's", names containing < or >)
    # don't break the rendered email body. Newlines are converted to
    # <br/> *after* escaping so the line breaks survive.
    paragraphs = "".join(
        f"<p style='margin:0 0 14px 0;'>"
        f"{html_escape(p.strip()).replace(chr(10), '<br/>')}"
        f"</p>"
        for p in text.strip().split("\n\n")
        if p.strip()
    )
    address_html = _format_address_html(business_address)
    return (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head><meta charset=\"UTF-8\"/></head>\n"
        "<body style=\"font-family:Arial,sans-serif;font-size:15px;line-height:1.6;"
        "color:#1E293B;max-width:580px;margin:40px auto;padding:0 20px;\">\n"
        f"  {paragraphs}\n"
        "  <hr style=\"border:none;border-top:1px solid #E2E8F0;margin:32px 0;\"/>\n"
        "  <p style=\"font-size:12px;color:#94A3B8;margin:0 0 8px 0;\">\n"
        f"    {sender_name} on behalf of {company_legal_name}<br/>\n"
        f"    {address_html}\n"
        "  </p>\n"
        "  <p style=\"font-size:12px;color:#94A3B8;margin:0;\">\n"
        f"    Don't want these emails? "
        f"<a href=\"{unsubscribe_url}\" style=\"color:#94A3B8;text-decoration:underline;\">"
        "Unsubscribe</a>.\n"
        "  </p>\n"
        "</body>\n"
        "</html>"
    )


# ── Email #1 — The Opener ────────────────────────────────────────

EMAIL_1_SUBJECT = "Friday nights at {{ restaurant_name }}"

EMAIL_1_TEXT = """\
Hi {{ first_name }},

{% if city -%}
Quick question for {{ city }} restaurant owners — how many calls does {{ restaurant_name }} miss on a Friday between 6 and 9pm?
{%- else -%}
Quick question — how many calls does {{ restaurant_name }} miss on a Friday between 6 and 9pm?
{%- endif %}

I ask because I'm building DialTone — voice AI that answers your phone, takes orders, and reads back the total to the customer. No app, no tablet, no extra staff. Works with your existing phone number.

Not pitching you anything today. Just looking for 10 minutes with restaurant owners who deal with this problem.

Worth a quick call this week?

— {{ from_name }}
DialTone.Menu
"""

# ── Email #2 — The Value Add ─────────────────────────────────────

EMAIL_2_SUBJECT = "The math on missed calls"

EMAIL_2_TEXT = """\
Hi {{ first_name }},

Didn't hear back — totally fine, I know Friday prep starts early.

One thing I've been calculating with restaurant owners lately:

10 missed calls per night × $35 avg order × 250 operating nights = $87,500/year walking out the door.

Not because the food was bad. Just because nobody picked up.

DialTone answers every call, even during the rush. I'd love to show you a 60-second demo — no commitment, no pitch deck.

Book a time here: {{ calendly_url }}

— {{ from_name }}
DialTone.Menu
"""

# ── Email #3 — Social Proof ──────────────────────────────────────

EMAIL_3_SUBJECT = "What other owners are saying"

EMAIL_3_TEXT = """\
Hi {{ first_name }},

One more try — promise I'll leave you alone after this if it's not relevant.

Talked to a Nashville restaurant owner last week. Busy 40-seat spot. Her reaction when she heard DialTone take an order:

"I didn't think it would sound like that."

That's the reaction I get most. People expect a phone tree. They get a conversation.

If you've got 10 minutes before the weekend rush, I'd love to show you the same demo.

Book a time here: {{ calendly_url }}

— {{ from_name }}
DialTone.Menu
"""

# ── Email #4 — Breakup ───────────────────────────────────────────

EMAIL_4_SUBJECT = "Closing the loop"

EMAIL_4_TEXT = """\
Hi {{ first_name }},

I've reached out a few times — clearly the timing isn't right, or this isn't a problem you're losing sleep over. Both are completely valid.

I'll stop following up after this one.

If missed calls during peak hours ever become something you want to solve, DialTone will be live this year at dialtone.menu. First restaurants on the waitlist get 60 days free and locked-in founder pricing.

Wishing {{ restaurant_name }} a great season either way.

— {{ from_name }}
DialTone.Menu
"""

# ── Email #5 — Re-engage (60 days, openers only) ─────────────────

EMAIL_5_SUBJECT = "Checking back in — DialTone update"

EMAIL_5_TEXT = """\
Hi {{ first_name }},

It's been a couple months since I reached out about DialTone.

Quick update: we've completed our first pilot restaurants and the early results have been strong — restaurants are capturing calls they would have missed every single weekend.

We're opening a small second cohort before general launch. Pilot restaurants get 60 days free and founder pricing locked in permanently.

Still just looking for 10 minutes if you're curious.

Book a time: {{ calendly_url }}

— {{ from_name }}
DialTone.Menu
"""

# ── Template registry ─────────────────────────────────────────────

TEMPLATES = {
    1: (EMAIL_1_SUBJECT, EMAIL_1_TEXT),
    2: (EMAIL_2_SUBJECT, EMAIL_2_TEXT),
    3: (EMAIL_3_SUBJECT, EMAIL_3_TEXT),
    4: (EMAIL_4_SUBJECT, EMAIL_4_TEXT),
    5: (EMAIL_5_SUBJECT, EMAIL_5_TEXT),
}

# Fallbacks shown when the imported contact has no usable values.
RESTAURANT_FALLBACK = "your restaurant"
FIRST_NAME_FALLBACK = "there"


def render_email(
    sequence_number: int,
    first_name: str,
    restaurant_name: str,
    city: str = "",
    calendly_url: str = CALENDLY_URL,
    from_name: str = FROM_NAME,
    to_email: str | None = None,
) -> dict:
    """Render an email template for a given sequence number.

    Args:
        sequence_number: Position in the 5-email sequence (1-5).
        first_name: Owner first name; falls back to ``"there"`` if empty.
        restaurant_name: Restaurant / company name. Cleaned via
            :func:`clean_company_name` and falls back to
            ``"your restaurant"`` when empty.
        city: Optional city. When provided, the opener uses a city hook;
            otherwise the hook is omitted gracefully.
        calendly_url: Booking link inserted into CTAs.
        from_name: Display name used in the signature and footer.
        to_email: Optional recipient address; used to personalize the
            ``mailto:`` unsubscribe subject line.

    Returns:
        A dict with ``subject``, ``text``, and ``html`` keys.

    Raises:
        ValueError: If ``sequence_number`` is unknown, or if
            ``BUSINESS_ADDRESS`` is not configured (CAN-SPAM guard).
    """
    if sequence_number not in TEMPLATES:
        raise ValueError(f"No template for sequence number {sequence_number}")

    if not BUSINESS_ADDRESS:
        raise ValueError(
            "BUSINESS_ADDRESS is not configured. Set it in .env before "
            "rendering or sending email — CAN-SPAM requires a real "
            "physical postal address in every commercial email."
        )

    # ``scripts/import_contacts.process_apollo`` already runs
    # ``clean_company_name`` at import time, so for production sends
    # this call is a no-op (it's idempotent). It's kept as a defensive
    # net for the ``cli.py send-test`` path, ad-hoc callers, and any
    # legacy rows imported before the cleanup landed.
    cleaned_name = clean_company_name(restaurant_name)
    if not cleaned_name:
        cleaned_name = RESTAURANT_FALLBACK

    safe_first = (first_name or "").strip() or FIRST_NAME_FALLBACK
    safe_city = (city or "").strip()

    subject_tmpl, text_tmpl = TEMPLATES[sequence_number]

    ctx = {
        "first_name":      safe_first,
        "restaurant_name": cleaned_name,
        "city":            safe_city,
        "calendly_url":    calendly_url,
        "from_name":       from_name,
    }

    subject = _render(subject_tmpl, **ctx).strip()
    body    = _render(text_tmpl, **ctx)

    unsubscribe_url = _resolve_unsubscribe_url(to_email)

    text = body + _text_footer(
        unsubscribe_url    = unsubscribe_url,
        business_address   = BUSINESS_ADDRESS,
        company_legal_name = COMPANY_LEGAL_NAME,
        sender_name        = from_name,
    )

    html = _html_wrap(
        body,
        unsubscribe_url    = unsubscribe_url,
        business_address   = BUSINESS_ADDRESS,
        company_legal_name = COMPANY_LEGAL_NAME,
        sender_name        = from_name,
    )

    return {"subject": subject, "text": text, "html": html}
