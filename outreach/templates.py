"""
templates.py — All outreach email templates with personalisation tokens.

Each template function returns a dict:
  { "subject": str, "text": str, "html": str }

Available tokens (passed as kwargs):
  first_name        — owner first name (or "there" as fallback)
  restaurant_name   — restaurant name
  city              — city
  calendly_url      — booking link
  from_name         — sender name
"""
from __future__ import annotations
from jinja2 import Template
from outreach.config import CALENDLY_URL, FROM_NAME


def _render(tmpl: str, **kwargs) -> str:
    return Template(tmpl).render(**kwargs)


def _html_wrap(text: str) -> str:
    """Wrap plain text in a minimal, clean HTML email."""
    paragraphs = "".join(
        f"<p style='margin:0 0 14px 0;'>{p.strip()}</p>"
        for p in text.strip().split("\n\n")
        if p.strip()
    )
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"/></head>
<body style="font-family:Arial,sans-serif;font-size:15px;line-height:1.6;
             color:#1E293B;max-width:580px;margin:40px auto;padding:0 20px;">
  {paragraphs}
  <hr style="border:none;border-top:1px solid #E2E8F0;margin:32px 0;"/>
  <p style="font-size:12px;color:#94A3B8;margin:0;">
    DialTone &middot; dialtone.menu &middot; Nashville, TN<br/>
    <a href="{{{{ unsubscribe_url }}}}" style="color:#94A3B8;">Unsubscribe</a>
  </p>
</body>
</html>"""


# ── Email #1 — The Opener ────────────────────────────────────────

EMAIL_1_SUBJECT = "Friday nights at {{ restaurant_name }}"

EMAIL_1_TEXT = """\
Hi {{ first_name }},

Quick question — how many calls does {{ restaurant_name }} miss on a Friday between 6 and 9pm?

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


def render_email(
    sequence_number: int,
    first_name: str,
    restaurant_name: str,
    city: str = "",
    calendly_url: str = CALENDLY_URL,
    from_name: str = FROM_NAME,
) -> dict:
    """
    Render an email template for a given sequence number.
    Returns { subject, text, html }.
    """
    if sequence_number not in TEMPLATES:
        raise ValueError(f"No template for sequence number {sequence_number}")

    subject_tmpl, text_tmpl = TEMPLATES[sequence_number]

    ctx = {
        "first_name":       first_name or "there",
        "restaurant_name":  restaurant_name,
        "city":             city,
        "calendly_url":     calendly_url,
        "from_name":        from_name,
    }

    subject = _render(subject_tmpl, **ctx)
    text    = _render(text_tmpl, **ctx)
    html    = _html_wrap(text.replace("\n\n", "</p><p>").replace("\n", "<br/>"))

    return {"subject": subject, "text": text, "html": html}
