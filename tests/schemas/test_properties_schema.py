"""
Schema tests for properties.
Targets validator branches and edge cases.
"""

import pytest
from pydantic import ValidationError
from decimal import Decimal

from app.schemas.properties import PropertyCreate, PropertyUpdate


class TestPropertySchemaValidation:
    """Property schema validation tests."""

    def test_property_create_rejects_non_positive_size(self):
        """property_size must be positive on create if provided."""
        with pytest.raises(ValidationError):
            PropertyCreate(
                title="Test",
                description="Test description",
                price=Decimal("1000000"),
                listing_type="sale",
                property_size=Decimal("0"),
            )

    def test_property_update_rejects_non_positive_price(self):
        """price must be positive on update if provided."""
        with pytest.raises(ValidationError):
            PropertyUpdate(price=Decimal("0"))

    def test_property_update_rejects_negative_counts(self):
        """bedrooms/bathrooms/parking_spaces must be non-negative."""
        with pytest.raises(ValidationError):
            PropertyUpdate(bedrooms=-1)

    def test_property_update_rejects_non_positive_size(self):
        """property_size must be positive on update if provided."""
        with pytest.raises(ValidationError):
            PropertyUpdate(property_size=Decimal("0"))

    def test_property_update_rejects_year_built_out_of_range(self):
        """year_built must be within allowed range on update."""
        with pytest.raises(ValidationError):
            PropertyUpdate(year_built=1900)
