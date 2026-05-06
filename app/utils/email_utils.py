# app/utils/email_utils.py
import logging
from typing import Optional

import resend
from resend.emails._emails import Emails
from resend.exceptions import ResendError

from app.core.config import settings


PLACEHOLDER_SENDER_VALUES = {
    "RealtorNet <no-reply@your-domain.com>",
    "RealtorNet <noreply@yourdomain.com>",
    "no-reply@your-domain.com",
    "noreply@yourdomain.com",
}

logger = logging.getLogger(__name__)


def is_email_dry_run_enabled() -> bool:
    """Return True when email delivery must not make an external API call."""
    return settings.EMAIL_DRY_RUN or settings.TESTING or settings.ENV == "test"


def _sender_address() -> str | None:
    sender = (settings.MAIL_FROM or settings.EMAIL_FROM).strip()
    if not sender or sender in PLACEHOLDER_SENDER_VALUES:
        return None
    return sender


def _missing_resend_settings() -> list[str]:
    missing = []
    if not settings.RESEND_API_KEY.strip():
        missing.append("RESEND_API_KEY")
    if _sender_address() is None:
        missing.append("MAIL_FROM or EMAIL_FROM")
    return missing


async def send_email(
    to_email: str,
    subject: str,
    text: Optional[str] = None,
    html: Optional[str] = None,
) -> bool:
    """
    Send an email using Resend.

    Test and explicit dry-run environments return success without performing an
    SDK call so automated suites can exercise email flows safely.
    """
    if is_email_dry_run_enabled():
        return True

    resend.api_key = settings.RESEND_API_KEY
    sender = _sender_address()

    missing_settings = _missing_resend_settings()
    if missing_settings:
        raise ValueError(
            "Resend settings are not properly configured: "
            + ", ".join(missing_settings)
        )
    assert sender is not None

    payload: Emails.SendParams = {
        "from": sender,
        "to": [to_email],
        "subject": subject,
    }
    if html:
        payload["html"] = html
    if text:
        payload["text"] = text
    if not html and not text:
        payload["text"] = ""

    try:
        response = resend.Emails.send(payload)
        if isinstance(response, dict) and response.get("id"):
            return True
        logger.warning(
            "Resend email send returned an unexpected response",
            extra={
                "response": response,
                "recipient": to_email,
                "subject": subject,
            },
        )
        return False
    except ResendError as exc:
        logger.warning(
            "Resend email send rejected",
            extra={
                "recipient": to_email,
                "subject": subject,
                "error": str(exc),
            },
        )
        return False
    except Exception as exc:
        raise RuntimeError("Email sending failed") from exc
