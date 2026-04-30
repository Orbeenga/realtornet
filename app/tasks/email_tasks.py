# app/tasks/email_tasks.py
"""
Celery tasks for email operations.
Handles async email sending within Celery's sync task context.
"""

import asyncio
import logging
from typing import Any, NoReturn, Optional
from urllib.parse import urlencode

from app.core.celery_config import celery_app
from app.core.config import settings
from app.utils.email_utils import send_email


logger = logging.getLogger(__name__)


def _run_send_email(
    *,
    task_name: str,
    to_email: str,
    subject: str,
    text: Optional[str] = None,
    html: Optional[str] = None,
) -> str:
    success = asyncio.run(
        send_email(
            to_email=to_email,
            subject=subject,
            text=text,
            html=html,
        )
    )

    if not success:
        raise RuntimeError("Email service returned failure status")

    logger.info(
        "%s email sent successfully to %s",
        task_name,
        to_email,
        extra={"recipient": to_email, "subject": subject},
    )
    return f"{task_name} email sent to {to_email}"


def _retry_or_raise(task: Any, exc: Exception, *, to_email: str, task_name: str) -> NoReturn:
    logger.error(
        "Failed to send %s email to %s",
        task_name,
        to_email,
        extra={
            "recipient": to_email,
            "error": str(exc),
            "retry_count": task.request.retries,
        },
        exc_info=True,
    )
    if task.request.retries < task.max_retries:
        raise task.retry(exc=exc, countdown=60 * (2 ** task.request.retries))
    raise exc


def _frontend_url(path: str, query: dict[str, str] | None = None) -> str:
    base_url = settings.FRONTEND_BASE_URL.rstrip("/")
    normalized_path = path if path.startswith("/") else f"/{path}"
    if query:
        return f"{base_url}{normalized_path}?{urlencode(query)}"
    return f"{base_url}{normalized_path}"


def dispatch_email_task(task: Any, *args: Any, **kwargs: Any) -> None:
    """
    Dispatch a transactional email without making endpoint success depend on it.

    Railway currently runs this backend as a single web process. The default
    synchronous path gives us real delivery without requiring a separate Celery
    worker; setting EMAIL_DELIVERY_MODE=celery preserves the async path.
    """
    try:
        if settings.EMAIL_DELIVERY_MODE.lower() == "celery":
            task.delay(*args, **kwargs)
            return
        result = task.apply(args=args, kwargs=kwargs)
        result.get(propagate=True)
    except Exception:
        logger.warning(
            "Transactional email dispatch failed; continuing without blocking request",
            extra={"task": getattr(task, "name", repr(task))},
            exc_info=True,
        )


@celery_app.task(
    name="app.tasks.email_tasks.send_welcome_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60  # Retry after 60 seconds
)
def send_welcome_email(
    self,
    to_email: str,
    subject: str,
    text: Optional[str] = None,
    html: Optional[str] = None
):
    """
    Background task to send a welcome email.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        text: Plain text body (optional)
        html: HTML body (optional)
    
    Returns:
        Success message string
        
    Raises:
        Exception: Re-raises after max retries
        
    Note: This task wraps the async send_email function and runs it
    in an event loop since Celery tasks are synchronous.
    """
    try:
        return _run_send_email(
            task_name="Welcome",
            to_email=to_email,
            subject=subject,
            text=text,
            html=html,
        )
    except Exception as exc:
        _retry_or_raise(self, exc, to_email=to_email, task_name="welcome")


@celery_app.task(
    name="app.tasks.email_tasks.send_verification_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def send_verification_email(
    self,
    to_email: str,
    verification_code: str,
    user_name: str
):
    """
    Send email verification code to new user.
    
    Args:
        to_email: Recipient email address
        verification_code: Verification code to include
        user_name: User's name for personalization
    """
    subject = "Verify Your RealtorNet Account"
    
    # HTML template for verification email
    html_body = f"""
    <html>
        <body>
            <h2>Welcome to RealtorNet, {user_name}!</h2>
            <p>Thank you for registering. Please verify your email address using the code below:</p>
            <div style="background-color: #f0f0f0; padding: 20px; text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 4px;">
                {verification_code}
            </div>
            <p>This code will expire in 24 hours.</p>
            <p>If you didn't create this account, please ignore this email.</p>
        </body>
    </html>
    """
    
    text_body = f"""
    Welcome to RealtorNet, {user_name}!
    
    Thank you for registering. Please verify your email address using this code:
    
    {verification_code}
    
    This code will expire in 24 hours.
    If you didn't create this account, please ignore this email.
    """
    
    try:
        return _run_send_email(
            task_name="Verification",
            to_email=to_email,
            subject=subject,
            text=text_body,
            html=html_body,
        )
    except Exception as exc:
        _retry_or_raise(self, exc, to_email=to_email, task_name="verification")


@celery_app.task(
    name="app.tasks.email_tasks.send_agency_approval_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_agency_approval_email(
    self,
    to_email: str,
    agency_name: str,
) -> str:
    """Notify an applicant that their agency application was approved."""
    login_url = _frontend_url("/login")
    subject = "Your agency application was approved"
    text_body = (
        f"Good news - {agency_name} has been approved on RealtorNet.\n\n"
        f"Sign in to manage your agency dashboard: {login_url}"
    )
    html_body = f"""
    <html>
        <body>
            <h2>Your agency application was approved</h2>
            <p>Good news - <strong>{agency_name}</strong> has been approved on RealtorNet.</p>
            <p><a href="{login_url}">Sign in to manage your agency dashboard</a></p>
        </body>
    </html>
    """
    try:
        return _run_send_email(
            task_name="Agency approval",
            to_email=to_email,
            subject=subject,
            text=text_body,
            html=html_body,
        )
    except Exception as exc:
        _retry_or_raise(self, exc, to_email=to_email, task_name="agency approval")


@celery_app.task(
    name="app.tasks.email_tasks.send_agency_rejection_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_agency_rejection_email(
    self,
    to_email: str,
    agency_name: str,
    reason: Optional[str] = None,
) -> str:
    """Notify an applicant that their agency application was not approved."""
    subject = "Agency application update"
    reason_text = f"\n\nReason: {reason}" if reason else ""
    reason_html = f"<p><strong>Reason:</strong> {reason}</p>" if reason else ""
    text_body = (
        f"Your agency application for {agency_name} was not approved at this time."
        f"{reason_text}\n\nYou can update your details and contact support if you need help."
    )
    html_body = f"""
    <html>
        <body>
            <h2>Agency application update</h2>
            <p>Your agency application for <strong>{agency_name}</strong> was not approved at this time.</p>
            {reason_html}
            <p>You can update your details and contact support if you need help.</p>
        </body>
    </html>
    """
    try:
        return _run_send_email(
            task_name="Agency rejection",
            to_email=to_email,
            subject=subject,
            text=text_body,
            html=html_body,
        )
    except Exception as exc:
        _retry_or_raise(self, exc, to_email=to_email, task_name="agency rejection")


@celery_app.task(
    name="app.tasks.email_tasks.send_agent_invitation_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_agent_invitation_email(
    self,
    to_email: str,
    agency_name: str,
    invite_token: str,
) -> str:
    """Invite an agent to join an agency."""
    invite_url = _frontend_url("/agency-invitations/accept", {"invite_token": invite_token})
    subject = f"You have been invited to join {agency_name}"
    text_body = (
        f"{agency_name} invited you to join their agency on RealtorNet.\n\n"
        f"Accept your invitation within 72 hours: {invite_url}"
    )
    html_body = f"""
    <html>
        <body>
            <h2>You have been invited to join {agency_name}</h2>
            <p>{agency_name} invited you to join their agency on RealtorNet.</p>
            <p><a href="{invite_url}">Accept your invitation</a></p>
            <p>This invitation expires in 72 hours.</p>
        </body>
    </html>
    """
    try:
        return _run_send_email(
            task_name="Agent invitation",
            to_email=to_email,
            subject=subject,
            text=text_body,
            html=html_body,
        )
    except Exception as exc:
        _retry_or_raise(self, exc, to_email=to_email, task_name="agent invitation")


@celery_app.task(
    name="app.tasks.email_tasks.send_join_request_status_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_join_request_status_email(
    self,
    to_email: str,
    agency_name: str,
    status_value: str,
    reason: Optional[str] = None,
) -> str:
    """Notify a requester that their agency join request was accepted or declined."""
    normalized_status = status_value.lower()
    accepted = normalized_status in {"accepted", "approved"}
    subject = f"Your request to join {agency_name} was {'accepted' if accepted else 'declined'}"
    reason_text = f"\n\nReason: {reason}" if reason else ""
    reason_html = f"<p><strong>Reason:</strong> {reason}</p>" if reason else ""
    next_step = (
        "You can now sign in and manage your agent dashboard."
        if accepted
        else "You can contact the agency owner if you need more information."
    )
    text_body = (
        f"Your request to join {agency_name} was {'accepted' if accepted else 'declined'}."
        f"{reason_text}\n\n{next_step}"
    )
    html_body = f"""
    <html>
        <body>
            <h2>Join request {'accepted' if accepted else 'declined'}</h2>
            <p>Your request to join <strong>{agency_name}</strong> was {'accepted' if accepted else 'declined'}.</p>
            {reason_html}
            <p>{next_step}</p>
        </body>
    </html>
    """
    try:
        return _run_send_email(
            task_name="Join request status",
            to_email=to_email,
            subject=subject,
            text=text_body,
            html=html_body,
        )
    except Exception as exc:
        _retry_or_raise(self, exc, to_email=to_email, task_name="join request status")


# Export task functions
__all__ = [
    "dispatch_email_task",
    "send_welcome_email",
    "send_verification_email",
    "send_agency_approval_email",
    "send_agency_rejection_email",
    "send_agent_invitation_email",
    "send_join_request_status_email",
]
