"""
Schema tests for saved searches.
Targets validator branches and edge cases.
"""

import pytest
from pydantic import ValidationError

from app.schemas.saved_searches import SavedSearchCreate, SavedSearchUpdate


class TestSavedSearchSchemaValidation:
    """SavedSearch schema validation tests."""

    def test_saved_search_create_rejects_empty_params(self):
        """Empty search_params should raise a validation error."""
        with pytest.raises(ValidationError):
            SavedSearchCreate(search_params={})

    def test_saved_search_create_strips_empty_name(self):
        """Empty name should normalize to None."""
        saved = SavedSearchCreate(search_params={"q": "lagos"}, name=" ")
        assert saved.name is None

    def test_saved_search_update_rejects_empty_params(self):
        """Empty search_params should raise a validation error on update."""
        with pytest.raises(ValidationError):
            SavedSearchUpdate(search_params={})

    def test_saved_search_update_strips_empty_name(self):
        """Empty update name should normalize to None."""
        saved = SavedSearchUpdate(name=" ")
        assert saved.name is None
