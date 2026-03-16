"""
Schema tests for property amenities.
Targets validator branches and edge cases.
"""

import pytest
from pydantic import ValidationError

from app.schemas.property_amenities import (
    PropertyAmenityCreate,
    PropertyAmenityBulkCreate,
    PropertyAmenitySync,
)


class TestPropertyAmenitySchemaValidation:
    """Property amenity schema validation tests."""

    def test_property_amenity_create_rejects_non_positive_ids(self):
        """Non-positive IDs should raise a validation error."""
        with pytest.raises(ValidationError):
            PropertyAmenityCreate(property_id=0, amenity_id=1)

    def test_property_amenity_bulk_rejects_empty_list(self):
        """Empty amenity_ids list should raise a validation error."""
        with pytest.raises(ValidationError):
            PropertyAmenityBulkCreate(property_id=1, amenity_ids=[])

    def test_property_amenity_bulk_rejects_negative_ids(self):
        """Negative IDs in amenity_ids should raise a validation error."""
        with pytest.raises(ValidationError):
            PropertyAmenityBulkCreate(property_id=1, amenity_ids=[1, -2])

    def test_property_amenity_bulk_dedupes_ids(self):
        """Bulk schema should remove duplicate IDs while preserving order."""
        bulk = PropertyAmenityBulkCreate(property_id=1, amenity_ids=[1, 2, 1, 3])
        assert bulk.amenity_ids == [1, 2, 3]

    def test_property_amenity_sync_rejects_negative_ids(self):
        """Sync schema should reject negative IDs."""
        with pytest.raises(ValidationError):
            PropertyAmenitySync(amenity_ids=[1, -1])

    def test_property_amenity_sync_dedupes_ids(self):
        """Sync schema should de-duplicate IDs."""
        sync = PropertyAmenitySync(amenity_ids=[1, 1, 2])
        assert set(sync.amenity_ids) == {1, 2}
