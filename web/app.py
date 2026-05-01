"""app.py — Local FastAPI web UI for DialTone Outreach.

Read + status-edit only. Sending stays in the CLI. Binds to
127.0.0.1 by design — no auth, no public exposure.

Start::

    uvicorn web.app:app --reload --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from outreach import db, sequence
from outreach.config import TERMINAL_STATUSES, Status
from outreach.templates import render_email

_DIR = Path(__file__).resolve().parent

app = FastAPI(title="DialTone Outreach", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=_DIR / "static"), name="static")
templates = Jinja2Templates(directory=_DIR / "templates")

# Status values exposed as edit buttons on the contact detail page.
# Sending-path statuses (emailed_1 … re_engage) are intentionally excluded.
EDITABLE_STATUSES = [
    Status.REPLIED,
    Status.DEMO_BOOKED,
    Status.PILOT,
    Status.CUSTOMER,
    Status.NOT_INTERESTED,
    Status.INVALID,
]

STATUS_ORDER = [
    "new", "emailed_1", "emailed_2", "emailed_3", "breakup_sent",
    "re_engage", "demo_booked", "pilot", "customer",
    "replied", "not_interested", "invalid",
]


# ── Dashboard ─────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Status counts, conversion funnel, emails sent today."""
    client = db.get_client()
    counts = db.get_status_counts(client)
    today = db.get_emails_sent_today(client)
    total = sum(counts.values())

    sent = sum(counts.get(s, 0) for s in
               ["emailed_1", "emailed_2", "emailed_3", "breakup_sent"])
    demos = counts.get("demo_booked", 0)
    pilots = counts.get("pilot", 0)
    customers = counts.get("customer", 0)

    funnel = {
        "email_to_demo": f"{demos / sent * 100:.1f}%" if sent else "—",
        "demo_to_pilot": f"{pilots / demos * 100:.1f}%" if demos else "—",
        "pilot_to_customer": f"{customers / pilots * 100:.1f}%" if pilots else "—",
    }

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "counts": counts,
        "total": total,
        "today": today,
        "sent": sent,
        "demos": demos,
        "pilots": pilots,
        "customers": customers,
        "funnel": funnel,
        "status_order": STATUS_ORDER,
        "page": "dashboard",
    })


# ── Contacts list ─────────────────────────────────────────────────


def _parse_score(raw: Optional[str]) -> Optional[int]:
    """Coerce an optional score query param to int or None."""
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


@app.get("/contacts", response_class=HTMLResponse)
async def contacts_list(
    request: Request,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    score: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
):
    """Searchable, filterable contacts table."""
    client = db.get_client()
    parsed_score = _parse_score(score)
    rows = db.search_contacts(
        client, q=q, status=status, score=parsed_score, city=city,
    )
    return templates.TemplateResponse("contacts.html", {
        "request": request,
        "contacts": rows,
        "q": q or "",
        "status": status or "",
        "score": parsed_score,
        "city": city or "",
        "status_order": STATUS_ORDER,
        "page": "contacts",
    })


@app.get("/partials/contacts", response_class=HTMLResponse)
async def contacts_partial(
    request: Request,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    score: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
):
    """HTMX partial — returns just the <tbody> rows."""
    client = db.get_client()
    rows = db.search_contacts(
        client, q=q, status=status, score=_parse_score(score), city=city,
    )
    return templates.TemplateResponse("partials/contact_rows.html", {
        "request": request,
        "contacts": rows,
    })


# ── Contact detail ────────────────────────────────────────────────


@app.get("/contacts/{contact_id}", response_class=HTMLResponse)
async def contact_detail(request: Request, contact_id: str):
    """Full contact info, email history, status buttons, notes."""
    client = db.get_client()
    contact = db.get_contact(client, contact_id)
    if not contact:
        return HTMLResponse("<h1>Contact not found</h1>", status_code=404)
    email_log = db.get_email_log_for_contact(client, contact_id)
    return templates.TemplateResponse("contact_detail.html", {
        "request": request,
        "c": contact,
        "email_log": email_log,
        "editable_statuses": EDITABLE_STATUSES,
        "page": "contacts",
    })


@app.post("/contacts/{contact_id}/status")
async def update_status(contact_id: str, status: str = Form(...)):
    """HTMX status update — redirect back to the contact detail."""
    if status not in {s for s in EDITABLE_STATUSES}:
        return HTMLResponse("Invalid status", status_code=400)
    client = db.get_client()
    db.update_contact_status(client, contact_id, status)
    return RedirectResponse(f"/contacts/{contact_id}", status_code=303)


@app.post("/contacts/{contact_id}/notes")
async def update_notes(contact_id: str, notes: str = Form("")):
    """HTMX notes save — redirect back to the contact detail."""
    client = db.get_client()
    db.update_contact_notes(client, contact_id, notes)
    return RedirectResponse(f"/contacts/{contact_id}", status_code=303)


# ── Run preview ───────────────────────────────────────────────────


@app.get("/run-preview", response_class=HTMLResponse)
async def run_preview(request: Request):
    """Read-only dry-run preview: which contacts would get emailed today."""
    client = db.get_client()
    due = sequence.get_contacts_due(client, limit=50)

    preview_rows = []
    for contact in due:
        seq_num = sequence.next_sequence_number(contact)
        if seq_num is None:
            continue
        try:
            email_data = render_email(
                sequence_number=seq_num,
                first_name=contact.get("owner_first", ""),
                restaurant_name=contact.get("restaurant_name", ""),
                city=contact.get("city", ""),
                to_email=contact.get("owner_email"),
            )
            subject = email_data["subject"]
        except Exception:
            subject = "(render error)"
        preview_rows.append({
            "id": contact["id"],
            "restaurant_name": contact.get("restaurant_name", "—"),
            "city": contact.get("city", "—"),
            "owner_email": contact.get("owner_email", "—"),
            "seq_num": seq_num,
            "lead_score": contact.get("lead_score", "—"),
            "subject": subject,
        })

    return templates.TemplateResponse("run_preview.html", {
        "request": request,
        "rows": preview_rows,
        "page": "run_preview",
    })
