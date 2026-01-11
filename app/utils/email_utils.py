# app/utils/email_utils.py
"""
Email utility functions using Mailgun (can be adapted for SendGrid, SMTP, etc.)
"""

import httpx
from typing import Optional
from app.core.config import settings


async def send_email(
    to_email: str,
    subject: str,
    text: Optional[str] = None,
    html: Optional[str] = None,
) -> bool:
    """
    Send an email using Mailgun API (placeholders can be replaced for other providers).
    """
    MAILGUN_API_KEY = settings.MAILGUN_API_KEY
    MAILGUN_DOMAIN = settings.MAILGUN_DOMAIN
    FROM_EMAIL = settings.MAIL_FROM

    if not MAILGUN_API_KEY or not MAILGUN_DOMAIN or not FROM_EMAIL:
        raise ValueError("Mailgun settings are not properly configured in .env")

    url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"

    data = {
        "from": FROM_EMAIL,
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
                auth=("api", MAILGUN_API_KEY),
                data=data,
                timeout=10,
            )
        return response.status_code == 200
    except Exception:
        # Optionally log error or integrate with a logger
        raise Exception(f"Email sending failed")