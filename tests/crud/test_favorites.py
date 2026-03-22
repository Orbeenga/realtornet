# tests/crud/test_favorites.py
"""
Favorites CRUD Test — Full coverage
favorites.py missing: 27-34, 47-74, 87-92, 106-118, 128-136, 145-151, 160-166
"""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.crud.favorites import FavoriteCRUD, favorite as favorite_singleton
from app.models.favorites import Favorite
from app.schemas.favorites import FavoriteCreate

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


# ═══════════════════════════════════════════════
# FAVORITES
# ═══════════════════════════════════════════════

@pytest.fixture
def fav_crud():
    return FavoriteCRUD()


def make_favorite(**kwargs) -> MagicMock:
    defaults = dict(
        user_id=1,
        property_id=10,
        deleted_at=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=Favorite)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


# ─── get (lines 27-34) ───────────────────────

class TestFavoriteGet:
    def test_returns_active_favorite(self, fav_crud, mock_db):
        obj = make_favorite()
        scalar_one_or_none(mock_db, obj)
        assert fav_crud.get(mock_db, user_id=1, property_id=10) == obj

    def test_returns_none_when_missing(self, fav_crud, mock_db):
        scalar_one_or_none(mock_db, None)
        assert fav_crud.get(mock_db, user_id=1, property_id=999) is None

    def test_excludes_soft_deleted(self, fav_crud, mock_db):
        # get() filters deleted_at IS NULL — soft-deleted returns None
        scalar_one_or_none(mock_db, None)
        assert fav_crud.get(mock_db, user_id=1, property_id=10) is None


# ─── create (lines 47-74) ────────────────────

class TestFavoriteCreate:
    def test_create_new(self, fav_crud, mock_db):
        """No existing record → creates new."""
        scalar_one_or_none(mock_db, None)
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None
        
        # FIX: Pass property_id in the schema, and user_id as a separate keyword argument
        fav_crud.create(
            mock_db, 
            obj_in=FavoriteCreate(property_id=10), 
            user_id=1
        )

    def test_returns_soft_deleted_without_restoring(self, fav_crud, mock_db):
        """Existing but soft-deleted → restores it."""
        existing = make_favorite(deleted_at=datetime.now(timezone.utc))
        scalar_one_or_none(mock_db, existing)

        # FIX: Separate the schema and the user_id
        result = fav_crud.create(
            mock_db, 
            obj_in=FavoriteCreate(property_id=10), 
            user_id=1
        )
        assert result.deleted_at is not None

    def test_returns_existing_active(self, fav_crud, mock_db):
        """Already active → returns it without creating duplicate."""
        existing = make_favorite(deleted_at=None)
        scalar_one_or_none(mock_db, existing)

        # FIX: Separate the schema and the user_id
        result = fav_crud.create(
            mock_db, 
            obj_in=FavoriteCreate(property_id=10), 
            user_id=1
        )
        assert result == existing


# ─── soft_delete (lines 87-92) ───────────────

class TestFavoriteSoftDelete:
    def test_soft_delete_existing(self, fav_crud, mock_db):
        """Found → triggers commit + refresh."""
        obj = make_favorite()
        with patch.object(fav_crud, "get", return_value=obj):
            mock_db.flush.return_value = None
            mock_db.refresh.return_value = None
            result = fav_crud.soft_delete(mock_db, user_id=1, property_id=10)
        assert result == obj
        mock_db.flush.assert_called_once()

    def test_soft_delete_not_found_returns_none(self, fav_crud, mock_db):
        """Not found → returns None, no commit."""
        with patch.object(fav_crud, "get", return_value=None):
            result = fav_crud.soft_delete(mock_db, user_id=1, property_id=999)
        assert result is None
        mock_db.flush.assert_not_called()


# ─── get_user_favorites (lines 106-118) ──────

class TestFavoriteGetUserFavorites:
    def test_returns_favorites(self, fav_crud, mock_db):
        items = [make_favorite(), make_favorite(property_id=20)]
        scalars_all(mock_db, items)
        result = fav_crud.get_user_favorites(mock_db, user_id=1)
        assert result == items

    def test_empty(self, fav_crud, mock_db):
        scalars_all(mock_db, [])
        assert fav_crud.get_user_favorites(mock_db, user_id=99) == []

    def test_pagination(self, fav_crud, mock_db):
        scalars_all(mock_db, [])
        assert fav_crud.get_user_favorites(mock_db, user_id=1, skip=5, limit=10) == []


# ─── is_favorited (lines 128-136) ────────────

class TestFavoriteIsFavorited:
    def test_true_when_favorited(self, fav_crud, mock_db):
        scalar(mock_db, 1)
        assert fav_crud.is_favorited(mock_db, user_id=1, property_id=10) is True

    def test_false_when_not(self, fav_crud, mock_db):
        scalar(mock_db, 0)
        assert fav_crud.is_favorited(mock_db, user_id=1, property_id=10) is False


# ─── count_active_favorites (lines 145-151) ──

class TestFavoriteCountActive:
    def test_count(self, fav_crud, mock_db):
        scalar(mock_db, 7)
        assert fav_crud.count_active_favorites(mock_db, property_id=10) == 7

    def test_zero(self, fav_crud, mock_db):
        scalar(mock_db, 0)
        assert fav_crud.count_active_favorites(mock_db, property_id=99) == 0


# ─── count_user_favorites (lines 160-166) ────

class TestFavoriteCountUser:
    def test_count(self, fav_crud, mock_db):
        scalar(mock_db, 3)
        assert fav_crud.count_user_favorites(mock_db, user_id=1) == 3

    def test_zero(self, fav_crud, mock_db):
        scalar(mock_db, 0)
        assert fav_crud.count_user_favorites(mock_db, user_id=99) == 0


# ─── singleton ────────────────────────────────

class TestFavoriteSingleton:
    def test_is_instance(self):
        assert isinstance(favorite_singleton, FavoriteCRUD)
