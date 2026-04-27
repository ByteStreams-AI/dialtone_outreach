"""
email_client.py — AWS SES wrapper for sending outreach emails
"""
from __future__ import annotations
import boto3
from botocore.exceptions import ClientError
from outreach.config import (
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION,
    FROM_FULL, FROM_EMAIL,
)


def get_ses_client():
    return boto3.client(
        "ses",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )


def send_email(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str = None,
    reply_to: str = None,
) -> dict:
    """
    Send a single email via AWS SES.
    Returns dict with message_id on success, raises on failure.
    """
    client = get_ses_client()

    message = {
        "Subject": {"Data": subject, "Charset": "UTF-8"},
        "Body": {"Text": {"Data": body_text, "Charset": "UTF-8"}},
    }

    if body_html:
        message["Body"]["Html"] = {"Data": body_html, "Charset": "UTF-8"}

    kwargs = {
        "Source": FROM_FULL,
        "Destination": {"ToAddresses": [to_email]},
        "Message": message,
    }

    if reply_to:
        kwargs["ReplyToAddresses"] = [reply_to]

    try:
        response = client.send_email(**kwargs)
        return {
            "success": True,
            "message_id": response["MessageId"],
        }
    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg  = e.response["Error"]["Message"]
        raise RuntimeError(f"SES error [{code}]: {msg}") from e


def verify_sender_identity(email: str) -> None:
    """
    Trigger SES verification email for the sender address.
    Only needed once per address in sandbox mode.
    """
    client = get_ses_client()
    client.verify_email_identity(EmailAddress=email)
    print(f"Verification email sent to {email}. Check your inbox.")


def get_send_quota() -> dict:
    """Returns SES sending quota and usage for today."""
    client = get_ses_client()
    quota = client.get_send_quota()
    return {
        "max_24h":       quota["Max24HourSend"],
        "sent_last_24h": quota["SentLast24Hours"],
        "max_per_second":quota["MaxSendRate"],
        "remaining":     quota["Max24HourSend"] - quota["SentLast24Hours"],
    }


def is_in_sandbox() -> bool:
    """
    Heuristic: if max 24h send is 200, we're still in SES sandbox.
    Request production access at:
    https://console.aws.amazon.com/ses/home#/account
    """
    quota = get_send_quota()
    return quota["max_24h"] <= 200
