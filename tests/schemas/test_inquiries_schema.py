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


class TestInquiryReplySchemaValidation:

    def test_reply_create_valid_body(self):
        from app.schemas.inquiries import InquiryReplyCreate
        reply = InquiryReplyCreate(body="Thanks for your interest")
        assert reply.body == "Thanks for your interest"

    def test_reply_create_rejects_empty_body(self):
        from app.schemas.inquiries import InquiryReplyCreate
        with pytest.raises(ValidationError):
            InquiryReplyCreate(body=" ")

    def test_reply_create_rejects_blank_body(self):
        from app.schemas.inquiries import InquiryReplyCreate
        with pytest.raises(ValidationError):
            InquiryReplyCreate(body="")
