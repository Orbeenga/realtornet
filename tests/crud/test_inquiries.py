# tests/crud/test_inquiries.py
"""
Inquiries CRUD Tests — Full coverage
inquiries.py missing: 28-38, 47-53, 66-73, 86-103, 115-122, 133-145,
                      156-168, 182-196, 209-217, 226, 235, 244-250, 260-267
"""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.crud.inquiries import InquiryCRUD, inquiry as inquiry_singleton
from app.models.inquiries import Inquiry
from app.schemas.inquiries import InquiryCreate, InquiryUpdate


# ─────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────

@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)


def scalar_one_or_none(mock_db, value):
    mock_db.execute.return_value.scalar_one_or_none.return_value = value


def scalars_all(mock_db, value):
    mock_db.execute.return_value.scalars.return_value.all.return_value = value


def scalar(mock_db, value):
    mock_db.execute.return_value.scalar.return_value = value


def first_result(mock_db, **fields):
    """Wire db.execute().first() to a MagicMock row with named attributes."""
    row = MagicMock()
    for k, v in fields.items():
        setattr(row, k, v)
    mock_db.execute.return_value.first.return_value = row
    return row


# ═══════════════════════════════════════════════
# INQUIRIES
# ═══════════════════════════════════════════════

@pytest.fixture
def inq_crud():
    return InquiryCRUD()


def make_inquiry(**kwargs) -> MagicMock:
    defaults = dict(
        inquiry_id=1,
        user_id=1,
        property_id=10,
        message="Is this still available?",
        inquiry_status="new",
        deleted_at=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=Inquiry)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


# ─── create (lines 28-38) ────────────────────

class TestInquiryCreate:
    def test_create(self, inq_crud, mock_db):
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        inq_crud.create(mock_db,
                        obj_in=InquiryCreate(property_id=10, message="Interested"),
                        user_id=1)
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    def test_sets_user_id(self, inq_crud, mock_db):
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        inq_crud.create(mock_db,
                        obj_in=InquiryCreate(property_id=10, message="Hello"),
                        user_id=42)
        added = mock_db.add.call_args[0][0]
        assert added.user_id == 42


# ─── get (lines 47-53) ───────────────────────

class TestInquiryGet:
    def test_found(self, inq_crud, mock_db):
        obj = make_inquiry()
        scalar_one_or_none(mock_db, obj)
        assert inq_crud.get(mock_db, inquiry_id=1) == obj

    def test_not_found(self, inq_crud, mock_db):
        scalar_one_or_none(mock_db, None)
        assert inq_crud.get(mock_db, inquiry_id=999) is None


# ─── get_multi (lines 66-73) ─────────────────

class TestInquiryGetMulti:
    def test_returns_list(self, inq_crud, mock_db):
        items = [make_inquiry(), make_inquiry(inquiry_id=2)]
        scalars_all(mock_db, items)
        assert inq_crud.get_multi(mock_db) == items

    def test_empty(self, inq_crud, mock_db):
        scalars_all(mock_db, [])
        assert inq_crud.get_multi(mock_db) == []

    def test_pagination(self, inq_crud, mock_db):
        scalars_all(mock_db, [])
        assert inq_crud.get_multi(mock_db, skip=5, limit=10) == []


# ─── update (lines 86-103) ───────────────────

class TestInquiryUpdate:
    def test_not_found_returns_none(self, inq_crud, mock_db):
        with patch.object(inq_crud, "get", return_value=None):
            result = inq_crud.update(mock_db, inquiry_id=999,
                                     obj_in=InquiryUpdate(message="x"))
        assert result is None

    def test_update_message(self, inq_crud, mock_db):
        obj = make_inquiry(message="Old message")
        with patch.object(inq_crud, "get", return_value=obj):
            mock_db.flush.return_value = None
            mock_db.refresh.return_value = None
            inq_crud.update(mock_db, inquiry_id=1,
                            obj_in=InquiryUpdate(message="New message"))
        assert obj.message == "New message"

    def test_strips_protected_fields(self, inq_crud, mock_db):
        obj = make_inquiry(inquiry_id=1, user_id=5, property_id=10)
        with patch.object(inq_crud, "get", return_value=obj):
            mock_db.flush.return_value = None
            mock_db.refresh.return_value = None
            inq_crud.update(mock_db, inquiry_id=1,
                            obj_in=InquiryUpdate(message="safe"))
        assert obj.user_id == 5
        assert obj.property_id == 10


# ─── soft_delete (lines 115-122) ─────────────

class TestInquirySoftDelete:
    def test_found(self, inq_crud, mock_db):
        obj = make_inquiry()
        with patch.object(inq_crud, "get", return_value=obj):
            mock_db.flush.return_value = None
            mock_db.refresh.return_value = None
            result = inq_crud.soft_delete(mock_db, inquiry_id=1)
        assert result == obj
        assert obj.deleted_at is not None

    def test_not_found(self, inq_crud, mock_db):
        with patch.object(inq_crud, "get", return_value=None):
            result = inq_crud.soft_delete(mock_db, inquiry_id=999)
        assert result is None
        mock_db.flush.assert_not_called()


# ─── get_by_property (lines 133-145) ─────────

class TestInquiryGetByProperty:
    def test_returns_list(self, inq_crud, mock_db):
        items = [make_inquiry()]
        scalars_all(mock_db, items)
        assert inq_crud.get_by_property(mock_db, property_id=10) == items

    def test_empty(self, inq_crud, mock_db):
        scalars_all(mock_db, [])
        assert inq_crud.get_by_property(mock_db, property_id=99) == []

    def test_pagination(self, inq_crud, mock_db):
        scalars_all(mock_db, [])
        assert inq_crud.get_by_property(
            mock_db, property_id=10, skip=5, limit=10) == []


# ─── get_by_user (lines 156-168) ─────────────

class TestInquiryGetByUser:
    def test_returns_list(self, inq_crud, mock_db):
        items = [make_inquiry(user_id=1)]
        scalars_all(mock_db, items)
        assert inq_crud.get_by_user(mock_db, user_id=1) == items

    def test_empty(self, inq_crud, mock_db):
        scalars_all(mock_db, [])
        assert inq_crud.get_by_user(mock_db, user_id=99) == []

    def test_pagination(self, inq_crud, mock_db):
        scalars_all(mock_db, [])
        assert inq_crud.get_by_user(mock_db, user_id=1, skip=0, limit=5) == []


# ─── get_by_property_owner (lines 182-196) ───

class TestInquiryGetByPropertyOwner:
    def test_returns_list(self, inq_crud, mock_db):
        items = [make_inquiry()]
        scalars_all(mock_db, items)
        assert inq_crud.get_by_property_owner(mock_db, owner_user_id=5) == items

    def test_empty(self, inq_crud, mock_db):
        scalars_all(mock_db, [])
        assert inq_crud.get_by_property_owner(mock_db, owner_user_id=99) == []

    def test_pagination(self, inq_crud, mock_db):
        scalars_all(mock_db, [])
        assert inq_crud.get_by_property_owner(
            mock_db, owner_user_id=5, skip=2, limit=5) == []


# ─── update_status (lines 209-217) ───────────

class TestInquiryUpdateStatus:
    def test_not_found(self, inq_crud, mock_db):
        with patch.object(inq_crud, "get", return_value=None):
            result = inq_crud.update_status(mock_db, inquiry_id=999, new_status="viewed")
        assert result is None

    def test_updates_status(self, inq_crud, mock_db):
        obj = make_inquiry(inquiry_status="new")
        with patch.object(inq_crud, "get", return_value=obj):
            mock_db.flush.return_value = None
            mock_db.refresh.return_value = None
            inq_crud.update_status(mock_db, inquiry_id=1, new_status="viewed")
        assert obj.inquiry_status == "viewed"


# ─── mark_as_viewed / mark_as_responded (lines 226, 235) ─

class TestInquiryConvenienceMethods:
    def test_mark_as_viewed(self, inq_crud, mock_db):
        obj = make_inquiry(inquiry_status="new")
        with patch.object(inq_crud, "update_status", return_value=obj) as mock_us:
            inq_crud.mark_as_viewed(mock_db, inquiry_id=1)
        mock_us.assert_called_once_with(db=mock_db, inquiry_id=1, new_status="viewed")

    def test_mark_as_responded(self, inq_crud, mock_db):
        obj = make_inquiry(inquiry_status="viewed")
        with patch.object(inq_crud, "update_status", return_value=obj) as mock_us:
            inq_crud.mark_as_responded(mock_db, inquiry_id=1)
        mock_us.assert_called_once_with(db=mock_db, inquiry_id=1, new_status="responded")

    def test_mark_as_viewed_not_found(self, inq_crud, mock_db):
        with patch.object(inq_crud, "update_status", return_value=None):
            assert inq_crud.mark_as_viewed(mock_db, inquiry_id=999) is None

    def test_mark_as_responded_not_found(self, inq_crud, mock_db):
        with patch.object(inq_crud, "update_status", return_value=None):
            assert inq_crud.mark_as_responded(mock_db, inquiry_id=999) is None


# ─── count_by_property (lines 244-250) ───────

class TestInquiryCountByProperty:
    def test_count(self, inq_crud, mock_db):
        scalar(mock_db, 4)
        assert inq_crud.count_by_property(mock_db, property_id=10) == 4

    def test_zero(self, inq_crud, mock_db):
        scalar(mock_db, 0)
        assert inq_crud.count_by_property(mock_db, property_id=99) == 0


# ─── count_by_status (lines 260-267) ─────────

class TestInquiryCountByStatus:
    def test_count_new(self, inq_crud, mock_db):
        scalar(mock_db, 3)
        assert inq_crud.count_by_status(mock_db, property_id=10, status="new") == 3

    def test_count_viewed(self, inq_crud, mock_db):
        scalar(mock_db, 1)
        assert inq_crud.count_by_status(mock_db, property_id=10, status="viewed") == 1

    def test_count_responded(self, inq_crud, mock_db):
        scalar(mock_db, 0)
        assert inq_crud.count_by_status(mock_db, property_id=10, status="responded") == 0


# ─── singleton ────────────────────────────────

class TestInquirySingleton:
    def test_is_instance(self):
        assert isinstance(inquiry_singleton, InquiryCRUD)
