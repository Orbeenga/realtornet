import asyncio

import httpx
import pytest

from app.core.config import settings
from app.utils.email_utils import is_email_dry_run_enabled, send_email


def _set_live_sendgrid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "TESTING", False)
    monkeypatch.setattr(settings, "EMAIL_DRY_RUN", False)
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", "test-key")
    monkeypatch.setattr(settings, "MAIL_FROM", "no-reply@example.com")


def test_send_email_dry_run_skips_sendgrid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "EMAIL_DRY_RUN", True)
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "TESTING", False)

    assert is_email_dry_run_enabled() is True
    assert asyncio.run(send_email("agent@example.com", "Subject", text="Body")) is True


def test_send_email_requires_sendgrid_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "TESTING", False)
    monkeypatch.setattr(settings, "EMAIL_DRY_RUN", False)
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", "")
    monkeypatch.setattr(settings, "MAIL_FROM", "")

    with pytest.raises(ValueError, match="SENDGRID_API_KEY"):
        asyncio.run(send_email("agent@example.com", "Subject", text="Body"))


def test_send_email_falls_back_to_email_from_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_live_sendgrid(monkeypatch)
    monkeypatch.setattr(settings, "MAIL_FROM", "")
    monkeypatch.setattr(settings, "EMAIL_FROM", "RealtorNet <sender@example.com>")
    calls = []

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, *, headers, json, timeout):
            calls.append(json)
            return httpx.Response(202)

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    assert asyncio.run(send_email("agent@example.com", "Subject", text="Body")) is True
    assert calls[0]["from"] == {"email": "sender@example.com", "name": "RealtorNet"}


def test_send_email_rejects_placeholder_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_live_sendgrid(monkeypatch)
    monkeypatch.setattr(settings, "MAIL_FROM", "RealtorNet <no-reply@your-domain.com>")
    monkeypatch.setattr(settings, "EMAIL_FROM", "")

    with pytest.raises(ValueError, match="MAIL_FROM or EMAIL_FROM"):
        asyncio.run(send_email("agent@example.com", "Subject", text="Body"))


def test_send_email_posts_to_sendgrid(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_live_sendgrid(monkeypatch)
    calls = []

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, *, headers, json, timeout):
            calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
            return httpx.Response(202)

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    assert asyncio.run(send_email("agent@example.com", "Subject", text="Text", html="<p>HTML</p>")) is True
    assert calls == [
        {
            "url": "https://api.sendgrid.com/v3/mail/send",
            "headers": {
                "Authorization": "Bearer test-key",
                "Content-Type": "application/json",
            },
            "json": {
                "personalizations": [{"to": [{"email": "agent@example.com"}]}],
                "from": {"email": "no-reply@example.com"},
                "subject": "Subject",
                "content": [
                    {"type": "text/plain", "value": "Text"},
                    {"type": "text/html", "value": "<p>HTML</p>"},
                ],
            },
            "timeout": 10,
        }
    ]


def test_send_email_logs_warning_for_sendgrid_failure(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    _set_live_sendgrid(monkeypatch)

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, *, headers, json, timeout):
            return httpx.Response(403, text="sender identity is not verified")

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    caplog.set_level("WARNING", logger="app.utils.email_utils")

    assert asyncio.run(send_email("agent@example.com", "Subject", text="Body")) is False
    assert "SendGrid email send rejected" in caplog.text
    assert caplog.records[0].response_body == "sender identity is not verified"
    assert caplog.records[0].levelname == "WARNING"


def test_send_email_wraps_http_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_live_sendgrid(monkeypatch)

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, *, headers, json, timeout):
            raise httpx.ConnectError("network down")

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    with pytest.raises(RuntimeError, match="Email sending failed"):
        asyncio.run(send_email("agent@example.com", "Subject", text="Body"))
