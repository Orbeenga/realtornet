# app/utils/email_utils.py
from typing import Optional

import httpx

from app.core.config import settings


MAILGUN_SUCCESS_CODES = {200, 202}


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
    Send an email using Mailgun API.

    Test and explicit dry-run environments return success without performing an
    HTTP request so automated suites can exercise email flows safely.
    """
    if is_email_dry_run_enabled():
        return True

    mailgun_api_key = settings.MAILGUN_API_KEY
    mailgun_domain = settings.MAILGUN_DOMAIN
    from_email = settings.MAIL_FROM

    if not mailgun_api_key or not mailgun_domain or not from_email:
        raise ValueError("Mailgun settings are not properly configured in .env")

    url = f"https://api.mailgun.net/v3/{mailgun_domain}/messages"

    data = {
        "from": from_email,
        "to": to_email,
        "subject": subject,
    }

    if text:
        data["text"] = text
    if html:
        data["html"] = html

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                auth=("api", mailgun_api_key),
                data=data,
                timeout=10,
            )
        return response.status_code in MAILGUN_SUCCESS_CODES
    except Exception as exc:
        raise RuntimeError("Email sending failed") from exc
