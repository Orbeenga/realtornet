from typing import Any, cast
import runpy
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.config import settings
from app.tasks import email_tasks


@pytest.fixture(autouse=True)
def sync_email_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "EMAIL_DELIVERY_MODE", "sync")
    monkeypatch.setattr(settings, "EMAIL_DRY_RUN", True)
    monkeypatch.setattr(settings, "FRONTEND_BASE_URL", "https://realtornet-web.test")
    monkeypatch.setattr(settings, "BACKEND_BASE_URL", "https://api.realtornet.test")


def _patch_send_email(monkeypatch: pytest.MonkeyPatch, return_value: bool = True) -> AsyncMock:
    mock_send = AsyncMock(return_value=return_value)
    monkeypatch.setattr(email_tasks, "send_email", mock_send)
    return mock_send


def _sent_payload(mock_send: AsyncMock) -> dict[str, Any]:
    assert mock_send.await_args is not None
    return dict(mock_send.await_args.kwargs)


def test_welcome_email_task_sends_custom_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_send = _patch_send_email(monkeypatch)

    task = cast(Any, email_tasks.send_welcome_email)
    result = task.apply(
        args=("agent@example.com", "Welcome", "Plain", "<p>HTML</p>")
    ).get()

    assert result == "Welcome email sent to agent@example.com"
    assert _sent_payload(mock_send)["subject"] == "Welcome"
    assert _sent_payload(mock_send)["html"] == "<p>HTML</p>"


def test_verification_email_task_builds_code_message(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_send = _patch_send_email(monkeypatch)

    task = cast(Any, email_tasks.send_verification_email)
    result = task.apply(
        args=("agent@example.com", "123456", "Ada")
    ).get()

    assert result == "Verification email sent to agent@example.com"
    payload = _sent_payload(mock_send)
    assert payload["subject"] == "Verify Your RealtorNet Account"
    assert "123456" in payload["text"]
    assert "Ada" in payload["html"]


def test_agency_approval_email_contains_login_cta(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_send = _patch_send_email(monkeypatch)

    task = cast(Any, email_tasks.send_agency_approval_email)
    result = task.apply(
        args=("owner@example.com", "Prime Homes")
    ).get()

    assert result == "Agency approval email sent to owner@example.com"
    payload = _sent_payload(mock_send)
    assert payload["subject"] == "Your agency application was approved"
    assert "Prime Homes" in payload["text"]
    assert "https://realtornet-web.test/login" in payload["html"]


def test_agency_rejection_email_includes_optional_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_send = _patch_send_email(monkeypatch)

    task = cast(Any, email_tasks.send_agency_rejection_email)
    task.apply(
        args=("owner@example.com", "Prime Homes", "Incomplete documents")
    ).get()

    payload = _sent_payload(mock_send)
    assert payload["subject"] == "Agency application update"
    assert "Incomplete documents" in payload["text"]
    assert "Incomplete documents" in payload["html"]


def test_agent_invitation_email_contains_token_link_and_72_hour_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_send = _patch_send_email(monkeypatch)

    task = cast(Any, email_tasks.send_agent_invitation_email)
    task.apply(
        args=("agent@example.com", "Prime Homes", "signed.token")
    ).get()

    payload = _sent_payload(mock_send)
    assert payload["subject"] == "You have been invited to join Prime Homes"
    assert "/agencies/accept-invite?token=signed.token" in payload["text"]
    assert "72 hours" in payload["html"]


def test_agent_invitation_email_provider_rejection_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_send_email(monkeypatch, return_value=False)

    task = cast(Any, email_tasks.send_agent_invitation_email)
    result = task.apply(
        args=("agent@example.com", "Prime Homes", "signed.token")
    ).get()

    assert result == "Agent invitation email was not sent to agent@example.com"


def test_join_request_status_email_handles_decline_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_send = _patch_send_email(monkeypatch)

    task = cast(Any, email_tasks.send_join_request_status_email)
    task.apply(
        args=("seeker@example.com", "Prime Homes", "declined", "Portfolio too thin")
    ).get()

    payload = _sent_payload(mock_send)
    assert payload["subject"] == "Your request to join Prime Homes was declined"
    assert "Portfolio too thin" in payload["text"]


def test_inquiry_received_email_contains_lead_context(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_send = _patch_send_email(monkeypatch)

    task = cast(Any, email_tasks.send_inquiry_received_email)
    result = task.apply(
        args=(
            "agent@example.com",
            "Lekki Apartment",
            "Test User",
            "seeker@example.com",
            "+2347000000000",
            "Can I inspect tomorrow?",
            42,
        )
    ).get()

    assert result == "Inquiry received email sent to agent@example.com"
    payload = _sent_payload(mock_send)
    assert payload["subject"] == "New inquiry on Lekki Apartment"
    assert "Can I inspect tomorrow?" in payload["text"]
    assert "/account/inquiries" in payload["html"]
    assert "/properties/42" in payload["html"]


def test_inquiry_received_email_uses_phone_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_send = _patch_send_email(monkeypatch)

    task = cast(Any, email_tasks.send_inquiry_received_email)
    task.apply(
        args=(
            "agent@example.com",
            "Lekki Apartment",
            "Test User",
            "seeker@example.com",
            None,
            "Can I inspect tomorrow?",
            42,
        )
    ).get()

    assert "Phone: Not provided" in _sent_payload(mock_send)["text"]


def test_backend_url_adds_query_string() -> None:
    assert (
        email_tasks._backend_url("/unsubscribe", {"token": "abc"})
        == "https://api.realtornet.test/unsubscribe?token=abc"
    )


def test_property_moderation_email_includes_outcome_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_send = _patch_send_email(monkeypatch)

    task = cast(Any, email_tasks.send_property_moderation_email)
    result = task.apply(
        args=("agent@example.com", "Lekki Apartment", "rejected", 42, "Photos are unclear")
    ).get()

    assert result == "Property moderation email sent to agent@example.com"
    payload = _sent_payload(mock_send)
    assert payload["subject"] == "Listing update - Lekki Apartment"
    assert "Photos are unclear" in payload["text"]
    assert "/account/listings" in payload["html"]


def test_saved_search_match_email_includes_listing_and_unsubscribe(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_send = _patch_send_email(monkeypatch)

    task = cast(Any, email_tasks.send_saved_search_match_email)
    result = task.apply(
        args=(
            "seeker@example.com",
            "Lekki 2BR",
            "Lekki Apartment",
            "NGN 45,000,000.00",
            42,
            "00000000-0000-0000-0000-000000000001",
            "https://cdn.example.com/thumb.jpg",
        )
    ).get()

    assert result == "Saved search match email sent to seeker@example.com"
    payload = _sent_payload(mock_send)
    assert payload["subject"] == "New listing match: Lekki Apartment"
    assert "/properties/42" in payload["html"]
    assert "https://api.realtornet.test/api/v1/saved-searches/unsubscribe/00000000-0000-0000-0000-000000000001/" in payload["text"]
    assert "https://cdn.example.com/thumb.jpg" in payload["html"]


def test_role_change_email_includes_prior_and_new_role(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_send = _patch_send_email(monkeypatch)

    task = cast(Any, email_tasks.send_role_change_email)
    result = task.apply(
        args=("agent@example.com", "Test Agent", "agent", "seeker", "Membership revoked")
    ).get()

    assert result == "Role change email sent to agent@example.com"
    payload = _sent_payload(mock_send)
    assert payload["subject"] == "Your account role has been updated"
    assert "Previous role: agent" in payload["text"]
    assert "New role: seeker" in payload["text"]
    assert "Membership revoked" in payload["html"]


def test_review_request_status_email_includes_decision_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_send = _patch_send_email(monkeypatch)

    task = cast(Any, email_tasks.send_review_request_status_email)
    result = task.apply(
        args=("agent@example.com", "Test Agent", "Acme Realty", "declined", "Still missing documents")
    ).get()

    assert result == "Review request status email sent to agent@example.com"
    payload = _sent_payload(mock_send)
    assert payload["subject"] == "Your Acme Realty review request was declined"
    assert "Acme Realty has declined your review request." in payload["text"]
    assert "Still missing documents" in payload["html"]


def test_dispatch_email_task_uses_celery_delay_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "EMAIL_DELIVERY_MODE", "celery")
    task = Mock()

    email_tasks.dispatch_email_task(task, "one", named="two")

    task.delay.assert_called_once_with("one", named="two")
    task.apply.assert_not_called()


def test_dispatch_email_task_uses_local_apply_in_sync_mode() -> None:
    task = Mock()
    result = Mock()
    result.get.return_value = "sent"
    task.apply.return_value = result

    email_tasks.dispatch_email_task(task, "one", named="two")

    task.apply.assert_called_once_with(args=("one",), kwargs={"named": "two"})
    result.get.assert_called_once_with(propagate=True)
    task.delay.assert_not_called()


def test_dispatch_email_task_fail_open_for_sync_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    task = Mock()
    result = Mock()
    result.get.side_effect = RuntimeError("email provider unavailable")
    task.apply.return_value = result

    email_tasks.dispatch_email_task(task, "one")

    task.apply.assert_called_once()


@pytest.mark.parametrize(
    ("task", "args"),
    [
        (email_tasks.send_welcome_email, ("agent@example.com", "Welcome", "Plain", "<p>HTML</p>")),
        (email_tasks.send_verification_email, ("agent@example.com", "123456", "Ada")),
        (email_tasks.send_agency_approval_email, ("owner@example.com", "Prime Homes")),
        (email_tasks.send_agency_rejection_email, ("owner@example.com", "Prime Homes", "Incomplete documents")),
        (email_tasks.send_agent_invitation_email, ("agent@example.com", "Prime Homes", "signed.token")),
        (email_tasks.send_join_request_status_email, ("seeker@example.com", "Prime Homes", "declined", "Portfolio too thin")),
        (
            email_tasks.send_inquiry_received_email,
            (
                "agent@example.com",
                "Lekki Apartment",
                "Test User",
                "seeker@example.com",
                "+2347000000000",
                "Can I inspect tomorrow?",
                42,
            ),
        ),
        (email_tasks.send_property_moderation_email, ("agent@example.com", "Lekki Apartment", "rejected", 42, "Photos are unclear")),
        (
            email_tasks.send_saved_search_match_email,
            (
                "seeker@example.com",
                "Lekki 2BR",
                "Lekki Apartment",
                "NGN 45,000,000.00",
                42,
                "00000000-0000-0000-0000-000000000001",
            ),
        ),
        (email_tasks.send_role_change_email, ("agent@example.com", "Test Agent", "agent", "seeker", "Membership revoked")),
        (email_tasks.send_review_request_status_email, ("agent@example.com", "Test Agent", "Acme Realty", "declined", "Still missing documents")),
    ],
)
def test_email_tasks_retry_then_raise_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
    task: Any,
    args: tuple[Any, ...],
) -> None:
    monkeypatch.setattr(email_tasks, "send_email", AsyncMock(side_effect=RuntimeError("provider down")))

    with pytest.raises(RuntimeError, match="provider down"):
        cast(Any, task).apply(args=args).get(propagate=True)


def test_celery_worker_entrypoint_starts_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.celery_config import celery_app

    start = Mock()
    monkeypatch.setattr(celery_app, "start", start)

    runpy.run_module("app.celery_worker", run_name="__main__")

    start.assert_called_once_with()
