import asyncio

import pytest
import resend

from app.core.config import settings
from app.utils.email_utils import is_email_dry_run_enabled, send_email


def _set_live_resend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "TESTING", False)
    monkeypatch.setattr(settings, "EMAIL_DRY_RUN", False)
    monkeypatch.setattr(settings, "RESEND_API_KEY", "test-key")
    monkeypatch.setattr(settings, "MAIL_FROM", "no-reply@example.com")


def test_send_email_dry_run_skips_resend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "EMAIL_DRY_RUN", True)
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "TESTING", False)
    calls = []
    monkeypatch.setattr(resend.Emails, "send", lambda params: calls.append(params))

    assert is_email_dry_run_enabled() is True
    assert asyncio.run(send_email("agent@example.com", "Subject", text="Body")) is True
    assert calls == []


def test_send_email_requires_resend_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "TESTING", False)
    monkeypatch.setattr(settings, "EMAIL_DRY_RUN", False)
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")
    monkeypatch.setattr(settings, "MAIL_FROM", "")

    with pytest.raises(ValueError, match="RESEND_API_KEY"):
        asyncio.run(send_email("agent@example.com", "Subject", text="Body"))


def test_send_email_falls_back_to_email_from_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_live_resend(monkeypatch)
    monkeypatch.setattr(settings, "MAIL_FROM", "")
    monkeypatch.setattr(settings, "EMAIL_FROM", "RealtorNet <sender@example.com>")
    calls = []

    def fake_send(params):
        calls.append(params)
        return {"id": "email-id"}

    monkeypatch.setattr(resend.Emails, "send", fake_send)

    assert asyncio.run(send_email("agent@example.com", "Subject", text="Body")) is True
    assert calls[0]["from"] == "RealtorNet <sender@example.com>"


def test_send_email_rejects_placeholder_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_live_resend(monkeypatch)
    monkeypatch.setattr(settings, "MAIL_FROM", "RealtorNet <no-reply@your-domain.com>")
    monkeypatch.setattr(settings, "EMAIL_FROM", "")

    with pytest.raises(ValueError, match="MAIL_FROM or EMAIL_FROM"):
        asyncio.run(send_email("agent@example.com", "Subject", text="Body"))


def test_send_email_sends_with_resend(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_live_resend(monkeypatch)
    calls = []

    def fake_send(params):
        calls.append(params)
        return {"id": "email-id"}

    monkeypatch.setattr(resend.Emails, "send", fake_send)

    assert asyncio.run(send_email("agent@example.com", "Subject", text="Text", html="<p>HTML</p>")) is True
    assert calls == [
        {
            "from": "no-reply@example.com",
            "to": ["agent@example.com"],
            "subject": "Subject",
            "html": "<p>HTML</p>",
            "text": "Text",
        }
    ]


def test_send_email_logs_warning_for_resend_failure(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    _set_live_resend(monkeypatch)

    def fake_send(params):
        raise resend.exceptions.ValidationError(
            "sender identity is not verified",
            "validation_error",
            422,
        )

    monkeypatch.setattr(resend.Emails, "send", fake_send)

    caplog.set_level("WARNING", logger="app.utils.email_utils")

    assert asyncio.run(send_email("agent@example.com", "Subject", text="Body")) is False
    assert "Resend email send rejected" in caplog.text
    assert caplog.records[0].error == "sender identity is not verified"
    assert caplog.records[0].levelname == "WARNING"


def test_send_email_returns_false_for_unexpected_resend_response(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    _set_live_resend(monkeypatch)
    monkeypatch.setattr(resend.Emails, "send", lambda params: {"message": "queued"})

    caplog.set_level("WARNING", logger="app.utils.email_utils")

    assert asyncio.run(send_email("agent@example.com", "Subject", text="Body")) is False
    assert "Resend email send returned an unexpected response" in caplog.text


def test_send_email_wraps_unexpected_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_live_resend(monkeypatch)

    def fake_send(params):
        raise RuntimeError("network down")

    monkeypatch.setattr(resend.Emails, "send", fake_send)

    with pytest.raises(RuntimeError, match="Email sending failed"):
        asyncio.run(send_email("agent@example.com", "Subject", text="Body"))
