"""CRUD tests for InquiryReplyCRUD."""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.crud.inquiry_replies import InquiryReplyCRUD, inquiry_reply as reply_singleton
from app.models.inquiry_replies import InquiryReply


@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)


@pytest.fixture
def crud():
    return InquiryReplyCRUD()


def make_reply(**kwargs):
    defaults = dict(
        reply_id=1,
        inquiry_id=10,
        author_id=5,
        body="Thanks for your interest",
        created_at=datetime.now(timezone.utc),
        viewed_at=None,
        edited_at=None,
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=InquiryReply)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def scalar_one_or_none(mock_db, value):
    mock_db.execute.return_value.scalar_one_or_none.return_value = value


def scalars_all(mock_db, value):
    mock_db.execute.return_value.scalars.return_value.all.return_value = value


def scalar(mock_db, value):
    mock_db.execute.return_value.scalar.return_value = value


class TestCreate:

    def test_creates_reply(self, crud, mock_db):
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None

        result = crud.create(db=mock_db, inquiry_id=10, author_id=5, body="Nice property")

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
        mock_db.refresh.assert_called_once()
        added = mock_db.add.call_args[0][0]
        assert added.inquiry_id == 10
        assert added.author_id == 5
        assert added.body == "Nice property"


class TestGetByInquiry:

    def test_returns_list(self, crud, mock_db):
        items = [make_reply(), make_reply(reply_id=2)]
        scalars_all(mock_db, items)
        result = crud.get_by_inquiry(db=mock_db, inquiry_id=10)
        assert result == items

    def test_empty(self, crud, mock_db):
        scalars_all(mock_db, [])
        result = crud.get_by_inquiry(db=mock_db, inquiry_id=99)
        assert result == []

    def test_pagination(self, crud, mock_db):
        scalars_all(mock_db, [])
        result = crud.get_by_inquiry(db=mock_db, inquiry_id=10, skip=5, limit=10)
        assert result == []


class TestCountByInquiry:

    def test_returns_count(self, crud, mock_db):
        scalar(mock_db, 3)
        assert crud.count_by_inquiry(db=mock_db, inquiry_id=10) == 3

    def test_zero(self, crud, mock_db):
        scalar(mock_db, 0)
        assert crud.count_by_inquiry(db=mock_db, inquiry_id=99) == 0

    def test_none_becomes_zero(self, crud, mock_db):
        scalar(mock_db, None)
        assert crud.count_by_inquiry(db=mock_db, inquiry_id=10) == 0


class TestGetLatestByInquiry:

    def test_returns_latest(self, crud, mock_db):
        obj = make_reply()
        scalar_one_or_none(mock_db, obj)
        result = crud.get_latest_by_inquiry(db=mock_db, inquiry_id=10)
        assert result == obj

    def test_none_when_no_replies(self, crud, mock_db):
        scalar_one_or_none(mock_db, None)
        result = crud.get_latest_by_inquiry(db=mock_db, inquiry_id=99)
        assert result is None


class TestSingleton:

    def test_is_instance(self):
        assert isinstance(reply_singleton, InquiryReplyCRUD)
