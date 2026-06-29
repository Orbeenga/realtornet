import os
import re

PLACEHOLDER_NAME_PATTERNS: list[str] = [
    r"\bpreview\b",
    r"\btest\b",
    r"\bsmoke\b",
]

BLOCKED_EMAIL_DOMAINS: set[str] = {
    "smoke.realtornetapp.com",
    "resend.dev",
}

BLOCKED_EMAIL_PATTERNS: list[str] = [
    r"^preview[.\-]",
    r"\+test",
    r"@example\.com$",
    r"^smoke[.\-]",
]


def is_placeholder_name(name: str | None) -> bool:
    if not name:
        return False
    return any(re.search(p, name, re.IGNORECASE) for p in PLACEHOLDER_NAME_PATTERNS)


def is_test_email(email: str) -> bool:
    return any(re.search(p, email, re.IGNORECASE) for p in BLOCKED_EMAIL_PATTERNS)


def validate_not_placeholder(name: str | None, field_name: str = "name") -> str | None:
    if name and is_placeholder_name(name):
        raise ValueError(f"{field_name} contains a disallowed placeholder term")
    return name


def validate_not_test_email(email: str | None, field_name: str = "email") -> str | None:
    if email and is_test_email(email):
        raise ValueError(f"{field_name} appears to be a test address")
    return email
