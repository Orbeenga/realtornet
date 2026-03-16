"""
Schema tests for users.
Targets validator branches and edge cases.
"""

import pytest
from pydantic import ValidationError

from app.schemas.users import UserCreate, UserUpdate, UserLogin, UserRole


class TestUserSchemaValidation:
    """User schema validation tests."""

    def test_user_create_rejects_empty_names(self):
        """Empty first/last name should raise a validation error."""
        with pytest.raises(ValidationError):
            UserCreate(
                email="user@example.com",
                password="securepass123",
                first_name=" ",
                last_name="User",
                user_role=UserRole.SEEKER,
            )

    def test_user_create_strips_empty_phone_to_none(self):
        """Empty phone_number should normalize to None."""
        user = UserCreate(
            email="user2@example.com",
            password="securepass123",
            first_name="Test",
            last_name="User",
            phone_number=" ",
            user_role=UserRole.SEEKER,
        )
        assert user.phone_number is None

    def test_user_create_password_validator_rejects_short(self):
        """Directly exercise password validator branch for short values."""
        with pytest.raises(ValueError):
            UserCreate.validate_password("short")

    def test_user_update_rejects_empty_names(self):
        """Empty update fields should raise a validation error."""
        with pytest.raises(ValidationError):
            UserUpdate(first_name=" ")

    def test_user_update_strips_empty_phone_to_none(self):
        """Empty update phone_number should normalize to None."""
        update = UserUpdate(phone_number=" ")
        assert update.phone_number is None

    def test_user_login_lowercases_email(self):
        """Login email should normalize to lowercase."""
        login = UserLogin(email="USER@EXAMPLE.COM", password="password123")
        assert login.email == "user@example.com"
