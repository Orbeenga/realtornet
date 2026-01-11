# app/tasks/email_tasks.py
"""
Celery tasks for email operations.
Handles async email sending within Celery's sync task context.
"""

import asyncio
import logging
from typing import Optional

from app.core.celery_config import celery_app
from app.utils.email_utils import send_email


logger = logging.getLogger(__name__)


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
        # Run async function in sync context using asyncio.run()
        # This creates a new event loop for this task
        success = asyncio.run(
            send_email(
                to_email=to_email,
                subject=subject,
                text=text,
                html=html
            )
        )
        
        if success:
            logger.info(
                f"Welcome email sent successfully to {to_email}",
                extra={"recipient": to_email, "subject": subject}
            )
            return f"Welcome email sent to {to_email}"
        else:
            logger.error(
                f"Email send returned False for {to_email}",
                extra={"recipient": to_email}
            )
            raise Exception("Email service returned failure status")
            
    except Exception as exc:
        logger.error(
            f"Failed to send welcome email to {to_email}",
            extra={
                "recipient": to_email,
                "error": str(exc),
                "retry_count": self.request.retries
            },
            exc_info=True
        )
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        
        # Max retries reached - re-raise exception
        raise


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
        success = asyncio.run(
            send_email(
                to_email=to_email,
                subject=subject,
                text=text_body,
                html=html_body
            )
        )
        
        if success:
            logger.info(
                f"Verification email sent to {to_email}",
                extra={"recipient": to_email}
            )
            return f"Verification email sent to {to_email}"
        else:
            raise Exception("Email service returned failure status")
            
    except Exception as exc:
        logger.error(
            f"Failed to send verification email to {to_email}",
            extra={"recipient": to_email, "error": str(exc)},
            exc_info=True
        )
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        
        raise


# Export task functions
__all__ = ["send_welcome_email", "send_verification_email"]