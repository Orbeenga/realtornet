# app/utils/email_utils.py
from email.utils import parseaddr
from typing import Optional

import httpx

from app.core.config import settings


SENDGRID_MAIL_SEND_URL = "https://api.sendgrid.com/v3/mail/send"
SENDGRID_SUCCESS_CODES = {200, 202}
PLACEHOLDER_SENDER_VALUES = {
    "RealtorNet <no-reply@your-domain.com>",
    "RealtorNet <noreply@yourdomain.com>",
    "no-reply@your-domain.com",
    "noreply@yourdomain.com",
}


def is_email_dry_run_enabled() -> bool:
    """Return True when email delivery must not make an external API call."""
    return settings.EMAIL_DRY_RUN or settings.TESTING or settings.ENV == "test"


def _sender_payload() -> dict[str, str] | None:
    sender = (settings.MAIL_FROM or settings.EMAIL_FROM).strip()
    if not sender or sender in PLACEHOLDER_SENDER_VALUES:
        return None

    name, email = parseaddr(sender)
    if not email:
        return None

    payload = {"email": email}
    if name:
        payload["name"] = name
    return payload


def _missing_sendgrid_settings() -> list[str]:
    missing = []
    if not settings.SENDGRID_API_KEY.strip():
        missing.append("SENDGRID_API_KEY")
    if _sender_payload() is None:
        missing.append("MAIL_FROM or EMAIL_FROM")
    return missing


async def send_email(
    to_email: str,
    subject: str,
    text: Optional[str] = None,
    html: Optional[str] = None,
) -> bool:
    """
    Send an email using SendGrid's Mail Send API.

    Test and explicit dry-run environments return success without performing an
    HTTP request so automated suites can exercise email flows safely.
    """
    if is_email_dry_run_enabled():
        return True

    sendgrid_api_key = settings.SENDGRID_API_KEY
    sender = _sender_payload()

    missing_settings = _missing_sendgrid_settings()
    if missing_settings:
        raise ValueError(
            "SendGrid settings are not properly configured: "
            + ", ".join(missing_settings)
        )
    assert sender is not None

    content = []
    if text:
        content.append({"type": "text/plain", "value": text})
    if html:
        content.append({"type": "text/html", "value": html})
    if not content:
        content.append({"type": "text/plain", "value": ""})

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": sender,
        "subject": subject,
        "content": content,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SENDGRID_MAIL_SEND_URL,
                headers={
                    "Authorization": f"Bearer {sendgrid_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=10,
            )
        return response.status_code in SENDGRID_SUCCESS_CODES
    except Exception as exc:
        raise RuntimeError("Email sending failed") from exc
