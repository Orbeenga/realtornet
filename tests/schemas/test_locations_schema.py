"""
Schema tests for locations.
Targets validator branches and edge cases.
"""

import pytest
from pydantic import ValidationError

from app.schemas.locations import LocationBase, LocationUpdate


class TestLocationSchemaValidation:
    """Location schema validation tests."""

    def test_location_base_rejects_empty_required_fields(self):
        """Empty state/city should raise a validation error."""
        with pytest.raises(ValidationError):
            LocationBase(state=" ", city="Lagos")

    def test_location_base_strips_empty_neighborhood(self):
        """Empty neighborhood should normalize to None."""
        loc = LocationBase(state="Lagos", city="Ikeja", neighborhood=" ")
        assert loc.neighborhood is None

    def test_location_update_rejects_empty_required_fields(self):
        """Empty state/city should raise a validation error on update."""
        with pytest.raises(ValidationError):
            LocationUpdate(state=" ")
