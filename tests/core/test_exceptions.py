"""
tests/core/test_exceptions.py

Coverage harness for app/core/exceptions.py.
Targets the three global_exception_handler paths and the four ApplicationException
subclasses whose __init__ bodies were not reachable through existing tests.
"""
import asyncio
import json

from fastapi import HTTPException
from fastapi import Request

from app.core.exceptions import (
    ApplicationException,
    AuthenticationException,
    AuthorizationException,
    ErrorHandler,
    ResourceNotFoundException,
    ValidationException,
)


def _make_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "client": ("127.0.0.1", 9999),
        }
    )


# ---------------------------------------------------------------------------
# Exception subclass constructors
# ---------------------------------------------------------------------------

def test_validation_exception_has_correct_status_and_message():
    exc = ValidationException("bad input", details={"field": "email"})
    assert exc.status_code == 422
    assert exc.message == "bad input"
    assert exc.details == {"field": "email"}


def test_validation_exception_defaults_details_to_empty_dict():
    exc = ValidationException("missing value")
    assert exc.details == {}


def test_authorization_exception_uses_default_message():
    exc = AuthorizationException()
    assert exc.status_code == 403
    assert "denied" in exc.message.lower()


def test_authorization_exception_accepts_custom_message():
    exc = AuthorizationException("Forbidden resource")
    assert exc.message == "Forbidden resource"


def test_resource_not_found_exception_formats_message():
    exc = ResourceNotFoundException("Property", 42)
    assert exc.status_code == 404
    assert "Property" in exc.message
    assert "42" in exc.message


def test_authentication_exception_default_message():
    exc = AuthenticationException()
    assert exc.status_code == 401


# ---------------------------------------------------------------------------
# ErrorHandler.global_exception_handler — three dispatch paths
# ---------------------------------------------------------------------------

def test_global_handler_returns_application_exception_status():
    exc = ApplicationException("something broke", status_code=400)
    response = asyncio.run(ErrorHandler.global_exception_handler(_make_request(), exc))
    assert response.status_code == 400
    body = json.loads(bytes(response.body))
    assert body["message"] == "something broke"


def test_global_handler_returns_http_exception_status():
    exc = HTTPException(status_code=404, detail="Not found")
    response = asyncio.run(ErrorHandler.global_exception_handler(_make_request(), exc))
    assert response.status_code == 404
    body = json.loads(bytes(response.body))
    assert body["message"] == "Not found"


def test_global_handler_returns_500_for_generic_exception():
    exc = RuntimeError("totally unexpected")
    response = asyncio.run(ErrorHandler.global_exception_handler(_make_request(), exc))
    assert response.status_code == 500
    body = json.loads(bytes(response.body))
    assert body["status_code"] == 500
    assert body["details"]["exception_type"] == "RuntimeError"
