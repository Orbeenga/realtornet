"""
Schema tests for profiles.
Targets validator branches and edge cases.
"""

import pytest
from pydantic import ValidationError

from app.schemas.profiles import ProfileBase, ProfileUpdate


class TestProfileSchemaValidation:
    """Profile schema validation tests."""

    def test_profile_base_rejects_empty_full_name(self):
        """Empty full_name should raise a validation error."""
        with pytest.raises(ValidationError):
            ProfileBase(full_name=" ")

    def test_profile_base_strips_empty_optional_text(self):
        """Empty optional text should normalize to None."""
        profile = ProfileBase(full_name="Test User", phone_number=" ")
        assert profile.phone_number is None

    def test_profile_update_rejects_empty_full_name(self):
        """Empty full_name should raise a validation error on update."""
        with pytest.raises(ValidationError):
            ProfileUpdate(full_name=" ")

    def test_profile_update_strips_empty_optional_text(self):
        """Empty update optional text should normalize to None."""
        profile = ProfileUpdate(bio=" ")
        assert profile.bio is None
