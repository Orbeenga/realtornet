# app/utils/email_utils.py
from typing import Optional

import httpx

from app.core.config import settings


SENDGRID_MAIL_SEND_URL = "https://api.sendgrid.com/v3/mail/send"
SENDGRID_SUCCESS_CODES = {200, 202}


def is_email_dry_run_enabled() -> bool:
    """Return True when email delivery must not make an external API call."""
    return settings.EMAIL_DRY_RUN or settings.TESTING or settings.ENV == "test"


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
    from_email = settings.MAIL_FROM

    if not sendgrid_api_key or not from_email:
        raise ValueError("SendGrid settings are not properly configured in .env")

    content = []
    if text:
        content.append({"type": "text/plain", "value": text})
    if html:
        content.append({"type": "text/html", "value": html})
    if not content:
        content.append({"type": "text/plain", "value": ""})

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_email},
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
