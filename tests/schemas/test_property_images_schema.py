"""
Schema tests for property images.
Targets validator branches and edge cases.
"""

import pytest
from pydantic import ValidationError

from app.schemas.property_images import (
    PropertyImageCreate,
    PropertyImageUpdate,
    PropertyImageBulkCreate,
)


class TestPropertyImageSchemaValidation:
    """Property image schema validation tests."""

    def test_property_image_create_rejects_empty_url(self):
        """Empty image_url should raise a validation error."""
        with pytest.raises(ValidationError):
            PropertyImageCreate(property_id=1, image_url=" ")

    def test_property_image_update_rejects_empty_url(self):
        """Empty image_url should raise a validation error on update."""
        with pytest.raises(ValidationError):
            PropertyImageUpdate(image_url=" ")

    def test_property_image_bulk_rejects_empty_images(self):
        """Bulk create requires at least one image."""
        with pytest.raises(ValidationError):
            PropertyImageBulkCreate(property_id=1, images=[])
