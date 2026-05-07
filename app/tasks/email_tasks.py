# app/tasks/email_tasks.py
"""
Celery tasks for email operations.
Handles async email sending within Celery's sync task context.
"""

import asyncio
from html import escape
from typing import Any, NoReturn, Optional
from urllib.parse import urlencode

from app.core.celery_config import celery_app
from app.core.config import settings
from app.core.logging import logger
from app.utils.email_utils import send_email


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
        logger.warning(
            "%s email was not accepted by the email provider",
            task_name,
            extra={"recipient": to_email, "subject": subject},
        )
        return f"{task_name} email was not sent to {to_email}"

    logger.info(
        "%s email sent successfully to %s",
        task_name,
        to_email,
        extra={"recipient": to_email, "subject": subject},
    )
    return f"{task_name} email sent to {to_email}"


def _retry_or_raise(task: Any, exc: Exception, *, to_email: str, task_name: str) -> NoReturn:
    logger.warning(
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


def _backend_url(path: str, query: dict[str, str] | None = None) -> str:
    base_url = settings.BACKEND_BASE_URL.rstrip("/")
    normalized_path = path if path.startswith("/") else f"/{path}"
    if query:
        return f"{base_url}{normalized_path}?{urlencode(query)}"
    return f"{base_url}{normalized_path}"


def _display_value(value: str | None, fallback: str = "Not provided") -> str:
    value = (value or "").strip()
    return value if value else fallback


def dispatch_email_task(task: Any, *args: Any, **kwargs: Any) -> None:
    """
    Dispatch a transactional email without making endpoint success depend on it.

    Railway currently runs this backend as a single web process. The default
    synchronous path executes the Celery task locally via ``apply`` so no Redis
    queue or worker is involved. Setting EMAIL_DELIVERY_MODE=celery preserves
    the async path for deployments that run a worker.
    """
    task_name = getattr(task, "name", repr(task))
    try:
        if settings.EMAIL_DELIVERY_MODE.lower() == "celery":
            task.delay(*args, **kwargs)
            logger.info(
                f"Transactional email task queued for Celery worker: {task_name}",
            )
            return
        result = task.apply(args=args, kwargs=kwargs)
        task_result = result.get(propagate=True)
        logger.info(
            f"Transactional email task executed synchronously: {task_name} -> {task_result}",
        )
    except Exception:
        logger.warning(
            f"Transactional email dispatch failed for {task_name}; continuing without blocking request",
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
    requires_registration: bool = False,
) -> str:
    """Notify an applicant that their agency application was approved."""
    action_url = _frontend_url(
        "/register" if requires_registration else "/login",
        {"email": to_email} if requires_registration else None,
    )
    action_label = (
        "Create your owner account"
        if requires_registration
        else "Sign in to manage your agency dashboard"
    )
    subject = "Your agency application was approved"
    next_step = (
        "Create your RealtorNet owner account with this email address to manage your agency dashboard."
        if requires_registration
        else "Sign in to manage your agency dashboard."
    )
    text_body = (
        f"Good news - {agency_name} has been approved on RealtorNet.\n\n"
        f"{next_step}\n\n{action_label}: {action_url}"
    )
    html_body = f"""
    <html>
        <body>
            <h2>Your agency application was approved</h2>
            <p>Good news - <strong>{agency_name}</strong> has been approved on RealtorNet.</p>
            <p>{next_step}</p>
            <p><a href="{action_url}">{action_label}</a></p>
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
    invite_url = _frontend_url("/agencies/accept-invite", {"token": invite_token})
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


@celery_app.task(
    name="app.tasks.email_tasks.send_inquiry_received_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_inquiry_received_email(
    self,
    to_email: str,
    property_title: str,
    seeker_name: str,
    seeker_email: str,
    seeker_phone: Optional[str],
    message: str,
    property_id: int,
) -> str:
    """Notify a listing owner that a seeker sent a property inquiry."""
    dashboard_url = _frontend_url("/account/inquiries")
    property_url = _frontend_url(f"/properties/{property_id}")
    subject = f"New inquiry on {property_title}"
    seeker_phone_text = _display_value(seeker_phone)
    text_body = (
        f"You have a new inquiry on {property_title}.\n\n"
        f"Seeker: {seeker_name}\n"
        f"Email: {seeker_email}\n"
        f"Phone: {seeker_phone_text}\n\n"
        f"Message:\n{message}\n\n"
        f"View inquiries: {dashboard_url}\n"
        f"View listing: {property_url}"
    )
    html_body = f"""
    <html>
        <body>
            <h2>New inquiry on {escape(property_title)}</h2>
            <p>You have a new lead for <strong>{escape(property_title)}</strong>.</p>
            <p><strong>Seeker:</strong> {escape(seeker_name)}</p>
            <p><strong>Email:</strong> {escape(seeker_email)}</p>
            <p><strong>Phone:</strong> {escape(seeker_phone_text)}</p>
            <p><strong>Message:</strong></p>
            <p>{escape(message)}</p>
            <p><a href="{dashboard_url}">View inquiries</a></p>
            <p><a href="{property_url}">View listing</a></p>
        </body>
    </html>
    """
    try:
        return _run_send_email(
            task_name="Inquiry received",
            to_email=to_email,
            subject=subject,
            text=text_body,
            html=html_body,
        )
    except Exception as exc:
        _retry_or_raise(self, exc, to_email=to_email, task_name="inquiry received")


@celery_app.task(
    name="app.tasks.email_tasks.send_property_moderation_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_property_moderation_email(
    self,
    to_email: str,
    property_title: str,
    moderation_status: str,
    property_id: int,
    reason: Optional[str] = None,
) -> str:
    """Notify a listing owner about a moderation outcome."""
    normalized_status = moderation_status.lower()
    status_labels = {
        "verified": "Your listing is live",
        "rejected": "Listing update",
        "revoked": "Listing access change",
        "pending_review": "Listing returned to review",
    }
    subject = f"{status_labels.get(normalized_status, 'Listing moderation update')} - {property_title}"
    property_url = _frontend_url(f"/properties/{property_id}")
    dashboard_url = _frontend_url("/account/listings")
    reason_text = f"\n\nReason: {reason}" if reason else ""
    reason_html = f"<p><strong>Reason:</strong> {escape(reason)}</p>" if reason else ""
    if normalized_status == "verified":
        next_step = f"Your listing is now visible publicly: {property_url}"
        next_step_html = f'<p>Your listing is now visible publicly: <a href="{property_url}">View listing</a></p>'
    elif normalized_status == "rejected":
        next_step = "Please review the moderation note and update the listing before resubmitting."
        next_step_html = "<p>Please review the moderation note and update the listing before resubmitting.</p>"
    elif normalized_status == "revoked":
        next_step = "This listing is no longer publicly available. Contact support if you need a review."
        next_step_html = "<p>This listing is no longer publicly available. Contact support if you need a review.</p>"
    else:
        next_step = "Your listing is no longer public and is waiting for review."
        next_step_html = "<p>Your listing is no longer public and is waiting for review.</p>"

    text_body = (
        f"{status_labels.get(normalized_status, 'Listing moderation update')}: {property_title}."
        f"{reason_text}\n\n{next_step}\n\nManage listings: {dashboard_url}"
    )
    html_body = f"""
    <html>
        <body>
            <h2>{escape(status_labels.get(normalized_status, 'Listing moderation update'))}</h2>
            <p><strong>{escape(property_title)}</strong></p>
            {reason_html}
            {next_step_html}
            <p><a href="{dashboard_url}">Manage listings</a></p>
        </body>
    </html>
    """
    try:
        return _run_send_email(
            task_name="Property moderation",
            to_email=to_email,
            subject=subject,
            text=text_body,
            html=html_body,
        )
    except Exception as exc:
        _retry_or_raise(self, exc, to_email=to_email, task_name="property moderation")


@celery_app.task(
    name="app.tasks.email_tasks.send_saved_search_match_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_saved_search_match_email(
    self,
    to_email: str,
    search_name: Optional[str],
    property_title: str,
    property_price: str,
    property_id: int,
    unsubscribe_token: str,
    thumbnail_url: Optional[str] = None,
) -> str:
    """Notify a seeker that a newly verified listing matches a saved search."""
    property_url = _frontend_url(f"/properties/{property_id}")
    unsubscribe_url = _backend_url(f"/api/v1/saved-searches/unsubscribe/{unsubscribe_token}/")
    search_label = search_name or "your saved search"
    subject = f"New listing match: {property_title}"
    thumbnail_text = f"\nPhoto: {thumbnail_url}" if thumbnail_url else ""
    thumbnail_html = f'<p><img src="{escape(thumbnail_url)}" alt="{escape(property_title)}" style="max-width: 640px; width: 100%; height: auto;" /></p>' if thumbnail_url else ""
    text_body = (
        f"A new listing matches {search_label}.\n\n"
        f"{property_title}\n"
        f"Price: {property_price}"
        f"{thumbnail_text}\n\n"
        f"View listing: {property_url}\n"
        f"Unsubscribe from this saved search: {unsubscribe_url}"
    )
    html_body = f"""
    <html>
        <body>
            <h2>New listing match</h2>
            <p>A new listing matches <strong>{escape(search_label)}</strong>.</p>
            {thumbnail_html}
            <p><strong>{escape(property_title)}</strong></p>
            <p><strong>Price:</strong> {escape(property_price)}</p>
            <p><a href="{property_url}">View listing</a></p>
            <p><a href="{unsubscribe_url}">Unsubscribe from this saved search</a></p>
        </body>
    </html>
    """
    try:
        return _run_send_email(
            task_name="Saved search match",
            to_email=to_email,
            subject=subject,
            text=text_body,
            html=html_body,
        )
    except Exception as exc:
        _retry_or_raise(self, exc, to_email=to_email, task_name="saved search match")


@celery_app.task(
    name="app.tasks.email_tasks.send_role_change_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_role_change_email(
    self,
    to_email: str,
    user_name: str,
    prior_role: str,
    new_role: str,
    reason: Optional[str] = None,
) -> str:
    """Notify a user that their account role or access state changed."""
    account_url = _frontend_url("/account")
    subject = "Your account role has been updated"
    reason_text = f"\n\nReason: {reason}" if reason else ""
    reason_html = f"<p><strong>Reason:</strong> {escape(reason)}</p>" if reason else ""
    text_body = (
        f"Hello {user_name},\n\n"
        f"Your RealtorNet account access was updated.\n\n"
        f"Previous role: {prior_role}\n"
        f"New role: {new_role}"
        f"{reason_text}\n\n"
        f"Review your account: {account_url}"
    )
    html_body = f"""
    <html>
        <body>
            <h2>Your account role has been updated</h2>
            <p>Hello {escape(user_name)},</p>
            <p>Your RealtorNet account access was updated.</p>
            <p><strong>Previous role:</strong> {escape(prior_role)}</p>
            <p><strong>New role:</strong> {escape(new_role)}</p>
            {reason_html}
            <p><a href="{account_url}">Review your account</a></p>
        </body>
    </html>
    """
    try:
        return _run_send_email(
            task_name="Role change",
            to_email=to_email,
            subject=subject,
            text=text_body,
            html=html_body,
        )
    except Exception as exc:
        _retry_or_raise(self, exc, to_email=to_email, task_name="role change")


@celery_app.task(
    name="app.tasks.email_tasks.send_review_request_status_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_review_request_status_email(
    self,
    to_email: str,
    user_name: str,
    agency_name: str,
    status: str,
    reason: Optional[str] = None,
) -> str:
    """Notify a user that an agency reviewed their rejoin/review request."""
    agency_url = _frontend_url("/agencies")
    status_label = status.lower()
    subject = f"Your {agency_name} review request was {status_label}"
    reason_text = f"\n\nReason: {reason}" if reason else ""
    reason_html = f"<p><strong>Reason:</strong> {escape(reason)}</p>" if reason else ""
    text_body = (
        f"Hello {user_name},\n\n"
        f"{agency_name} has {status_label} your review request."
        f"{reason_text}\n\n"
        f"Browse agencies: {agency_url}"
    )
    html_body = f"""
    <html>
        <body>
            <h2>Review request {escape(status_label)}</h2>
            <p>Hello {escape(user_name)},</p>
            <p>{escape(agency_name)} has {escape(status_label)} your review request.</p>
            {reason_html}
            <p><a href="{agency_url}">Browse agencies</a></p>
        </body>
    </html>
    """
    try:
        return _run_send_email(
            task_name="Review request status",
            to_email=to_email,
            subject=subject,
            text=text_body,
            html=html_body,
        )
    except Exception as exc:
        _retry_or_raise(self, exc, to_email=to_email, task_name="review request status")


# Export task functions
__all__ = [
    "dispatch_email_task",
    "send_welcome_email",
    "send_verification_email",
    "send_agency_approval_email",
    "send_agency_rejection_email",
    "send_agent_invitation_email",
    "send_join_request_status_email",
    "send_inquiry_received_email",
    "send_property_moderation_email",
    "send_saved_search_match_email",
    "send_role_change_email",
    "send_review_request_status_email",
]
