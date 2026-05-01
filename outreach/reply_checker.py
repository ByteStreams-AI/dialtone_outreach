"""reply_checker.py — IMAP-based reply detection for inbound emails.

Connects to the mailbox specified by ``REPLY_CHECK_*`` env vars, scans
for unread messages from known contacts, and marks them as ``replied``
in Supabase so the sequence engine stops emailing them.

Usage::

    from outreach.reply_checker import check_replies
    summary = check_replies(dry_run=False)

Or via the CLI::

    python cli.py check-replies [--dry-run]

Scheduling (cron, EventBridge, etc.) is deferred to Milestone 6.
"""

from __future__ import annotations

import email
import imaplib
import logging
from dataclasses import dataclass, field
from email.header import decode_header
from email.utils import parseaddr
from typing import Optional

from rich.console import Console

from outreach import db
from outreach.config import (
    REPLY_CHECK_EMAIL,
    REPLY_CHECK_IMAP_HOST,
    REPLY_CHECK_IMAP_PORT,
    REPLY_CHECK_PASSWORD,
)

logger = logging.getLogger(__name__)
console = Console()


@dataclass
class ReplyMatch:
    """A single matched reply from the inbox.

    Attributes:
        sender_email: The ``From:`` address of the inbound message.
        subject: The decoded ``Subject:`` header.
        contact_id: UUID of the matched ``contacts`` row.
        restaurant_name: For display purposes.
        email_log_id: UUID of the most-recent ``email_log`` row that
            was marked as replied (may be ``None`` if no log existed).
    """

    sender_email: str
    subject: str
    contact_id: str
    restaurant_name: Optional[str] = None
    email_log_id: Optional[str] = None


@dataclass
class CheckRepliesResult:
    """Summary returned by :func:`check_replies`.

    Attributes:
        scanned: Total unread messages examined.
        matched: Replies from known contacts that were processed.
        skipped: Messages from unknown senders (not in ``contacts``).
        errors: Messages that failed during processing.
        matches: Details of each matched reply.
    """

    scanned: int = 0
    matched: int = 0
    skipped: int = 0
    errors: int = 0
    matches: list[ReplyMatch] = field(default_factory=list)


def _validate_config() -> None:
    """Raise ``ValueError`` if required IMAP env vars are missing."""
    missing = []
    if not REPLY_CHECK_EMAIL:
        missing.append("REPLY_CHECK_EMAIL")
    if not REPLY_CHECK_PASSWORD:
        missing.append("REPLY_CHECK_PASSWORD")
    if missing:
        raise ValueError(
            f"Reply checking requires {', '.join(missing)} in .env. "
            "See .env.example for documentation."
        )


def _connect() -> imaplib.IMAP4_SSL:
    """Open an IMAP4_SSL connection to the reply-check mailbox.

    Returns:
        An authenticated ``IMAP4_SSL`` instance.

    Raises:
        imaplib.IMAP4.error: On authentication or connection failure.
    """
    _validate_config()
    conn = imaplib.IMAP4_SSL(REPLY_CHECK_IMAP_HOST, REPLY_CHECK_IMAP_PORT)
    conn.login(REPLY_CHECK_EMAIL, REPLY_CHECK_PASSWORD)
    return conn


def _decode_header_value(raw: str) -> str:
    """Decode an RFC 2047-encoded header into a plain string.

    Args:
        raw: Raw header value, possibly MIME-encoded.

    Returns:
        Decoded UTF-8 string.
    """
    parts = decode_header(raw)
    decoded = []
    for fragment, charset in parts:
        if isinstance(fragment, bytes):
            decoded.append(fragment.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(fragment)
    return "".join(decoded)


def _extract_sender(msg: email.message.Message) -> str:
    """Extract the plain email address from a ``From:`` header.

    Args:
        msg: Parsed email message.

    Returns:
        Lowercase email address (e.g. ``owner@restaurant.com``).
    """
    _, addr = parseaddr(msg.get("From", ""))
    return addr.strip().lower()


def _extract_subject(msg: email.message.Message) -> str:
    """Extract and decode the ``Subject:`` header.

    Args:
        msg: Parsed email message.

    Returns:
        Decoded subject string, or ``"(no subject)"`` if absent.
    """
    raw = msg.get("Subject", "")
    if not raw:
        return "(no subject)"
    return _decode_header_value(raw)


def _process_reply(
    client,
    sender_email: str,
    subject: str,
    *,
    dry_run: bool = False,
) -> Optional[ReplyMatch]:
    """Match a sender to a contact and mark as replied.

    Args:
        client: Supabase client.
        sender_email: Lowercase email address of the reply sender.
        subject: Decoded subject line (for logging).
        dry_run: If ``True``, report the match without writing to the DB.

    Returns:
        A :class:`ReplyMatch` if the sender matched a contact, else ``None``.
    """
    contact = db.find_contact_by_owner_email(client, sender_email)
    if contact is None:
        return None

    contact_id = contact["id"]
    restaurant = contact.get("restaurant_name", "—")

    # Find the most recent email_log row for this contact.
    last_email = db.get_last_email_sent(client, contact_id)
    log_id = last_email["id"] if last_email else None

    if not dry_run:
        db.mark_contact_replied(client, contact_id)
        if log_id:
            db.mark_email_replied(client, log_id)

    return ReplyMatch(
        sender_email=sender_email,
        subject=subject,
        contact_id=contact_id,
        restaurant_name=restaurant,
        email_log_id=log_id,
    )


def check_replies(*, dry_run: bool = False) -> CheckRepliesResult:
    """Scan the reply-check mailbox for replies from known contacts.

    Connects to the IMAP mailbox, searches for UNSEEN messages, matches
    each sender against ``contacts.owner_email``, and marks matched
    contacts + email_log rows as replied.

    Messages from known contacts are marked as SEEN in IMAP after
    processing so they are not reprocessed on the next run. Messages
    from unknown senders are left UNSEEN.

    Args:
        dry_run: If ``True``, report what would happen without modifying
            the database or IMAP flags.

    Returns:
        A :class:`CheckRepliesResult` with counts and match details.
    """
    _validate_config()
    result = CheckRepliesResult()
    client = db.get_client()

    conn = _connect()
    try:
        conn.select("INBOX")
        _status, msg_nums = conn.search(None, "UNSEEN")
        if not msg_nums or not msg_nums[0]:
            return result

        uid_list = msg_nums[0].split()
        result.scanned = len(uid_list)

        for uid in uid_list:
            try:
                _status, msg_data = conn.fetch(uid, "(BODY.PEEK[])")
                if not msg_data or not msg_data[0]:
                    continue
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                sender = _extract_sender(msg)
                subject = _extract_subject(msg)

                if not sender:
                    result.skipped += 1
                    continue

                match = _process_reply(
                    client,
                    sender,
                    subject,
                    dry_run=dry_run,
                )

                if match:
                    result.matched += 1
                    result.matches.append(match)

                    label = (
                        "[yellow]DRY RUN[/yellow]" if dry_run else "[green]✓[/green]"
                    )
                    console.print(
                        f"  {label} Reply from [cyan]{match.restaurant_name}[/cyan]  "
                        f"<{sender}>  Subject: {subject[:60]}"
                    )

                    # Mark as SEEN so it isn't reprocessed.
                    if not dry_run:
                        conn.store(uid, "+FLAGS", "\\Seen")
                else:
                    result.skipped += 1
                    logger.debug("Skipped unknown sender: %s", sender)

            except Exception as exc:
                result.errors += 1
                logger.warning("Error processing message %s: %s", uid, exc)
                console.print(f"  [red]✗[/red] Error processing message: {exc}")

    finally:
        try:
            conn.close()
        except Exception:
            pass
        try:
            conn.logout()
        except Exception:
            pass

    return result
