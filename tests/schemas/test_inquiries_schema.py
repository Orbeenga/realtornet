"""
Schema tests for inquiries.
Targets validator branches and edge cases.
"""

import pytest
from pydantic import ValidationError

from app.schemas.inquiries import InquiryBase, InquiryCreate, InquiryUpdate


class TestInquirySchemaValidation:
    """Inquiry schema validation tests."""

    def test_inquiry_base_strips_empty_message(self):
        """Empty message should normalize to None in base schema."""
        inquiry = InquiryBase(property_id=1, message=" ")
        assert inquiry.message is None

    def test_inquiry_create_rejects_empty_message(self):
        """Create message must be non-empty."""
        with pytest.raises(ValidationError):
            InquiryCreate(property_id=1, message=" ")

    def test_inquiry_update_rejects_empty_message(self):
        """Update message must be non-empty if provided."""
        with pytest.raises(ValidationError):
            InquiryUpdate(message=" ")
