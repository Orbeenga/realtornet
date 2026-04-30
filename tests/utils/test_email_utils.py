import asyncio

import httpx
import pytest

from app.core.config import settings
from app.utils.email_utils import is_email_dry_run_enabled, send_email


def _set_live_mailgun(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "TESTING", False)
    monkeypatch.setattr(settings, "EMAIL_DRY_RUN", False)
    monkeypatch.setattr(settings, "MAILGUN_API_KEY", "test-key")
    monkeypatch.setattr(settings, "MAILGUN_DOMAIN", "mail.example.com")
    monkeypatch.setattr(settings, "MAIL_FROM", "RealtorNet <no-reply@example.com>")


def test_send_email_dry_run_skips_mailgun(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "EMAIL_DRY_RUN", True)
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "TESTING", False)

    assert is_email_dry_run_enabled() is True
    assert asyncio.run(send_email("agent@example.com", "Subject", text="Body")) is True


def test_send_email_requires_mailgun_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "TESTING", False)
    monkeypatch.setattr(settings, "EMAIL_DRY_RUN", False)
    monkeypatch.setattr(settings, "MAILGUN_API_KEY", "")
    monkeypatch.setattr(settings, "MAILGUN_DOMAIN", "")
    monkeypatch.setattr(settings, "MAIL_FROM", "")

    with pytest.raises(ValueError, match="Mailgun settings"):
        asyncio.run(send_email("agent@example.com", "Subject", text="Body"))


def test_send_email_posts_to_mailgun(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_live_mailgun(monkeypatch)
    calls = []

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, *, auth, data, timeout):
            calls.append({"url": url, "auth": auth, "data": data, "timeout": timeout})
            return httpx.Response(202)

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    assert asyncio.run(send_email("agent@example.com", "Subject", text="Text", html="<p>HTML</p>")) is True
    assert calls == [
        {
            "url": "https://api.mailgun.net/v3/mail.example.com/messages",
            "auth": ("api", "test-key"),
            "data": {
                "from": "RealtorNet <no-reply@example.com>",
                "to": "agent@example.com",
                "subject": "Subject",
                "text": "Text",
                "html": "<p>HTML</p>",
            },
            "timeout": 10,
        }
    ]


def test_send_email_returns_false_for_mailgun_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_live_mailgun(monkeypatch)

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, *, auth, data, timeout):
            return httpx.Response(500)

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    assert asyncio.run(send_email("agent@example.com", "Subject", text="Body")) is False


def test_send_email_wraps_http_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_live_mailgun(monkeypatch)

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, *, auth, data, timeout):
            raise httpx.ConnectError("network down")

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    with pytest.raises(RuntimeError, match="Email sending failed"):
        asyncio.run(send_email("agent@example.com", "Subject", text="Body"))
