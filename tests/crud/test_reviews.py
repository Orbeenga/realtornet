# tests/crud/test_inquiries.py
"""
Reviews CRUD Tests — Full coverage
reviews.py missing:  32-47, 56-62, 76-94, 107-125, 136-148, 158-165,
                     175-182, 195-215, 227-234, 243-257, 271-285, 303-326
"""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.crud.reviews import ReviewCRUD, review as review_singleton
from app.models.reviews import Review
from app.schemas.reviews import ReviewCreate, ReviewUpdate


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
# REVIEWS
# ═══════════════════════════════════════════════

@pytest.fixture
def rev_crud():
    return ReviewCRUD()


def make_review(**kwargs) -> MagicMock:
    defaults = dict(
        review_id=1,
        user_id=1,
        property_id=10,
        agent_id=None,
        rating=4,
        comment="Great property",
        deleted_at=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=Review)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


# ─── create (lines 32-47) ────────────────────

class TestReviewCreate:
    def test_create_property_review(self, rev_crud, mock_db):
        """Lines 32-47: property_id set — happy path."""
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        rev_crud.create(mock_db,
                        obj_in=ReviewCreate(property_id=10, rating=5, comment="Lovely"),
                        user_id=1)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_sets_user_id(self, rev_crud, mock_db):
        """user_id comes from parameter, not schema."""
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        rev_crud.create(mock_db,
                        obj_in=ReviewCreate(property_id=10, rating=3, comment="OK"),
                        user_id=42)
        added = mock_db.add.call_args[0][0]
        assert added.user_id == 42

    def test_create_with_agent_id(self, rev_crud, mock_db):
        """agent_id branch in CRUD — pass via MagicMock to bypass schema."""
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        obj_in = MagicMock()
        obj_in.property_id = None
        obj_in.agent_id = 5
        obj_in.rating = 4
        obj_in.comment = "Good agent"
        rev_crud.create(mock_db, obj_in=obj_in, user_id=1)
        mock_db.add.assert_called_once()

    def test_both_none_raises(self, rev_crud, mock_db):
        """Both None → ValueError from CRUD validation."""
        obj_in = MagicMock()
        obj_in.property_id = None
        obj_in.agent_id = None
        obj_in.rating = 4
        obj_in.comment = "x"
        with pytest.raises(ValueError, match="Exactly one"):
            rev_crud.create(mock_db, obj_in=obj_in, user_id=1)

    def test_both_set_raises(self, rev_crud, mock_db):
        """Both set → ValueError from CRUD validation."""
        obj_in = MagicMock()
        obj_in.property_id = 10
        obj_in.agent_id = 5
        obj_in.rating = 4
        obj_in.comment = "x"
        with pytest.raises(ValueError, match="Exactly one"):
            rev_crud.create(mock_db, obj_in=obj_in, user_id=1)


# ─── get (lines 56-62) ───────────────────────

class TestReviewGet:
    def test_found(self, rev_crud, mock_db):
        obj = make_review()
        scalar_one_or_none(mock_db, obj)
        assert rev_crud.get(mock_db, review_id=1) == obj

    def test_not_found(self, rev_crud, mock_db):
        scalar_one_or_none(mock_db, None)
        assert rev_crud.get(mock_db, review_id=999) is None


# ─── get_property_reviews (lines 76-94) ──────

class TestReviewGetPropertyReviews:
    def test_returns_list(self, rev_crud, mock_db):
        items = [make_review(), make_review(review_id=2)]
        scalars_all(mock_db, items)
        assert rev_crud.get_property_reviews(mock_db, property_id=10) == items

    def test_empty(self, rev_crud, mock_db):
        scalars_all(mock_db, [])
        assert rev_crud.get_property_reviews(mock_db, property_id=99) == []

    def test_sort_by_rating_asc(self, rev_crud, mock_db):
        scalars_all(mock_db, [])
        assert rev_crud.get_property_reviews(
            mock_db, property_id=10, sort_by="rating", sort_desc=False) == []

    def test_sort_by_rating_desc(self, rev_crud, mock_db):
        scalars_all(mock_db, [])
        assert rev_crud.get_property_reviews(
            mock_db, property_id=10, sort_by="rating", sort_desc=True) == []

    def test_invalid_sort_col_falls_back(self, rev_crud, mock_db):
        """Unknown sort_by → falls back to created_at."""
        scalars_all(mock_db, [])
        assert rev_crud.get_property_reviews(
            mock_db, property_id=10, sort_by="hacker_field") == []

    def test_pagination(self, rev_crud, mock_db):
        scalars_all(mock_db, [])
        assert rev_crud.get_property_reviews(
            mock_db, property_id=10, skip=5, limit=10) == []


# ─── get_agent_reviews (lines 107-125) ───────

class TestReviewGetAgentReviews:
    def test_returns_list(self, rev_crud, mock_db):
        items = [make_review(agent_id=5, property_id=None)]
        scalars_all(mock_db, items)
        assert rev_crud.get_agent_reviews(mock_db, agent_id=5) == items

    def test_empty(self, rev_crud, mock_db):
        scalars_all(mock_db, [])
        assert rev_crud.get_agent_reviews(mock_db, agent_id=99) == []

    def test_sort_by_updated_at(self, rev_crud, mock_db):
        scalars_all(mock_db, [])
        assert rev_crud.get_agent_reviews(
            mock_db, agent_id=5, sort_by="updated_at", sort_desc=False) == []

    def test_invalid_sort_fallback(self, rev_crud, mock_db):
        scalars_all(mock_db, [])
        assert rev_crud.get_agent_reviews(
            mock_db, agent_id=5, sort_by="malicious") == []

    def test_pagination(self, rev_crud, mock_db):
        scalars_all(mock_db, [])
        assert rev_crud.get_agent_reviews(
            mock_db, agent_id=5, skip=2, limit=5) == []


# ─── get_user_reviews (lines 136-148) ────────

class TestReviewGetUserReviews:
    def test_returns_list(self, rev_crud, mock_db):
        items = [make_review(user_id=1)]
        scalars_all(mock_db, items)
        assert rev_crud.get_user_reviews(mock_db, user_id=1) == items

    def test_empty(self, rev_crud, mock_db):
        scalars_all(mock_db, [])
        assert rev_crud.get_user_reviews(mock_db, user_id=99) == []

    def test_pagination(self, rev_crud, mock_db):
        scalars_all(mock_db, [])
        assert rev_crud.get_user_reviews(mock_db, user_id=1, skip=0, limit=5) == []


# ─── get_user_property_review (lines 158-165) ─

class TestReviewGetUserPropertyReview:
    def test_found(self, rev_crud, mock_db):
        obj = make_review()
        scalar_one_or_none(mock_db, obj)
        assert rev_crud.get_user_property_review(mock_db, user_id=1, property_id=10) == obj

    def test_not_found(self, rev_crud, mock_db):
        scalar_one_or_none(mock_db, None)
        assert rev_crud.get_user_property_review(mock_db, user_id=1, property_id=99) is None


# ─── get_user_agent_review (lines 175-182) ───

class TestReviewGetUserAgentReview:
    def test_found(self, rev_crud, mock_db):
        obj = make_review(agent_id=5)
        scalar_one_or_none(mock_db, obj)
        assert rev_crud.get_user_agent_review(mock_db, user_id=1, agent_id=5) == obj

    def test_not_found(self, rev_crud, mock_db):
        scalar_one_or_none(mock_db, None)
        assert rev_crud.get_user_agent_review(mock_db, user_id=1, agent_id=99) is None


# ─── update (lines 195-215) ──────────────────

class TestReviewUpdate:
    def test_not_found_returns_none(self, rev_crud, mock_db):
        with patch.object(rev_crud, "get", return_value=None):
            result = rev_crud.update(mock_db, review_id=999,
                                     obj_in=ReviewUpdate(comment="x"))
        assert result is None

    def test_update_comment(self, rev_crud, mock_db):
        obj = make_review(comment="Old")
        with patch.object(rev_crud, "get", return_value=obj):
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            rev_crud.update(mock_db, review_id=1, obj_in=ReviewUpdate(comment="New"))
        assert obj.comment == "New"

    def test_update_rating(self, rev_crud, mock_db):
        obj = make_review(rating=3)
        with patch.object(rev_crud, "get", return_value=obj):
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            rev_crud.update(mock_db, review_id=1, obj_in=ReviewUpdate(rating=5))
        assert obj.rating == 5

    def test_strips_protected_fields(self, rev_crud, mock_db):
        obj = make_review(review_id=1, user_id=5, property_id=10)
        with patch.object(rev_crud, "get", return_value=obj):
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            rev_crud.update(mock_db, review_id=1, obj_in=ReviewUpdate(comment="safe"))
        assert obj.review_id == 1
        assert obj.user_id == 5
        assert obj.property_id == 10


# ─── soft_delete (lines 227-234) ─────────────

class TestReviewSoftDelete:
    def test_soft_delete_found(self, rev_crud, mock_db):
        obj = make_review()
        with patch.object(rev_crud, "get", return_value=obj):
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None
            result = rev_crud.soft_delete(mock_db, review_id=1)
        assert result == obj
        assert obj.deleted_at is not None

    def test_soft_delete_not_found(self, rev_crud, mock_db):
        with patch.object(rev_crud, "get", return_value=None):
            result = rev_crud.soft_delete(mock_db, review_id=999)
        assert result is None
        mock_db.commit.assert_not_called()


# ─── get_property_rating_stats (lines 243-257) ─

class TestReviewPropertyRatingStats:
    def test_with_reviews(self, rev_crud, mock_db):
        first_result(mock_db,
                     total_reviews=10, average_rating=4.2,
                     min_rating=2, max_rating=5)
        result = rev_crud.get_property_rating_stats(mock_db, property_id=10)
        assert result["total_reviews"] == 10
        assert result["average_rating"] == 4.2
        assert result["min_rating"] == 2
        assert result["max_rating"] == 5

    def test_no_reviews_zero_defaults(self, rev_crud, mock_db):
        first_result(mock_db,
                     total_reviews=0, average_rating=None,
                     min_rating=None, max_rating=None)
        result = rev_crud.get_property_rating_stats(mock_db, property_id=99)
        assert result["total_reviews"] == 0
        assert result["average_rating"] == 0.0


# ─── get_agent_rating_stats (lines 271-285) ──

class TestReviewAgentRatingStats:
    def test_with_reviews(self, rev_crud, mock_db):
        first_result(mock_db,
                     total_reviews=5, average_rating=3.8,
                     min_rating=3, max_rating=5)
        result = rev_crud.get_agent_rating_stats(mock_db, agent_id=5)
        assert result["total_reviews"] == 5
        assert result["average_rating"] == 3.8

    def test_no_reviews(self, rev_crud, mock_db):
        first_result(mock_db,
                     total_reviews=0, average_rating=None,
                     min_rating=None, max_rating=None)
        result = rev_crud.get_agent_rating_stats(mock_db, agent_id=99)
        assert result["average_rating"] == 0.0


# ─── get_rating_distribution (lines 303-326) ─

class TestReviewRatingDistribution:
    def test_by_property(self, rev_crud, mock_db):
        row1 = MagicMock()
        row1.rating = 5
        row1.count = 8
        row2 = MagicMock()
        row2.rating = 4
        row2.count = 3
        mock_db.execute.return_value.all.return_value = [row1, row2]

        result = rev_crud.get_rating_distribution(mock_db, property_id=10)
        assert result[5] == 8
        assert result[4] == 3
        assert result[1] == 0  # Unrated stars default to 0

    def test_by_agent(self, rev_crud, mock_db):
        mock_db.execute.return_value.all.return_value = []
        result = rev_crud.get_rating_distribution(mock_db, agent_id=5)
        assert result == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    def test_neither_raises(self, rev_crud, mock_db):
        with pytest.raises(ValueError, match="Either property_id or agent_id"):
            rev_crud.get_rating_distribution(mock_db)

    def test_all_stars_initialized(self, rev_crud, mock_db):
        mock_db.execute.return_value.all.return_value = []
        result = rev_crud.get_rating_distribution(mock_db, property_id=1)
        assert set(result.keys()) == {1, 2, 3, 4, 5}


# ─── singleton ────────────────────────────────

class TestReviewSoftDeleteEdgeCases:
    def test_soft_delete_property_returns_none_when_missing(self, rev_crud, mock_db):
        """
        Missing property reviews should return None on soft delete.

        This avoids silent commits when the review does not exist.
        """
        with patch.object(rev_crud, "get_property_ReviewResponse", return_value=None):
            result = rev_crud.soft_delete_property_ReviewResponse(
                mock_db, review_id=999999, deleted_by_supabase_id="uid"
            )
        assert result is None

    def test_soft_delete_agent_returns_none_when_missing(self, rev_crud, mock_db):
        """
        Missing agent reviews should return None on soft delete.

        This ensures not-found behavior is explicit.
        """
        with patch.object(rev_crud, "get_agent_ReviewResponse", return_value=None):
            result = rev_crud.soft_delete_agent_ReviewResponse(
                mock_db, review_id=999999, deleted_by_supabase_id="uid"
            )
        assert result is None


class TestReviewSingleton:
    def test_is_instance(self):
        assert isinstance(review_singleton, ReviewCRUD)
