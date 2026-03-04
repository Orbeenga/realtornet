# tests/crud/test_property_images.py
"""
PropertyImage CRUD Tests — Full coverage
property_images.py missing: 29, 41-49, 58-65, 74, 100-140, 160-191, 203-230,
    245-251, 264-276, 291-307
"""

import pytest
from unittest.mock import MagicMock, patch, call
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.crud.property_images import PropertyImageCRUD, property_image as pi_singleton
from app.models.property_images import PropertyImage
from app.schemas.property_images import PropertyImageCreate, PropertyImageUpdate

@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)


def scalars_all(mock_db, value):
    mock_db.execute.return_value.scalars.return_value.all.return_value = value


def scalar(mock_db, value):
    mock_db.execute.return_value.scalar.return_value = value


def first_result(mock_db, value):
    mock_db.execute.return_value.first.return_value = value

# ═══════════════════════════════════════════════
# PROPERTY IMAGES
# ═══════════════════════════════════════════════

@pytest.fixture
def pi_crud():
    return PropertyImageCRUD()


def make_image(**kwargs) -> MagicMock:
    defaults = dict(
        image_id=1,
        property_id=10,
        image_url="https://example.com/img.jpg",
        caption="Front view",
        is_primary=False,
        display_order=0,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    obj = MagicMock(spec=PropertyImage)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


# ─── get (line 29) ───────────────────────────

class TestPIGet:
    def test_found(self, pi_crud, mock_db):
        obj = make_image()
        mock_db.get.return_value = obj
        assert pi_crud.get(mock_db, image_id=1) == obj

    def test_not_found(self, pi_crud, mock_db):
        mock_db.get.return_value = None
        assert pi_crud.get(mock_db, image_id=999) is None


# ─── get_by_property (lines 41-49) ───────────

class TestPIGetByProperty:
    def test_returns_ordered_list(self, pi_crud, mock_db):
        items = [make_image(is_primary=True), make_image(image_id=2, is_primary=False)]
        mock_db.execute.return_value.scalars.return_value.all.return_value = items
        assert pi_crud.get_by_property(mock_db, property_id=10) == items

    def test_empty(self, pi_crud, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        assert pi_crud.get_by_property(mock_db, property_id=99) == []


# ─── get_primary_image (lines 58-65) ─────────

class TestPIGetPrimaryImage:
    def test_found(self, pi_crud, mock_db):
        obj = make_image(is_primary=True)
        mock_db.execute.return_value.scalar_one_or_none.return_value = obj
        assert pi_crud.get_primary_image(mock_db, property_id=10) == obj

    def test_none(self, pi_crud, mock_db):
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        assert pi_crud.get_primary_image(mock_db, property_id=99) is None


# ─── count_property_images (line 74) ─────────

class TestPICountPropertyImages:
    def test_count(self, pi_crud, mock_db):
        scalar(mock_db, 4)
        assert pi_crud.count_property_images(mock_db, property_id=10) == 4

    def test_zero(self, pi_crud, mock_db):
        scalar(mock_db, 0)
        assert pi_crud.count_property_images(mock_db, property_id=99) == 0


# ─── create (lines 100-140) ──────────────────

class TestPICreate:
    def test_property_not_found_raises(self, pi_crud, mock_db):
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="Property with id"):
            pi_crud.create(mock_db, obj_in=PropertyImageCreate(
                property_id=999, image_url="https://x.com/a.jpg"))

    def test_first_image_auto_primary(self, pi_crud, mock_db):
        """First image → is_primary forced True."""
        mock_db.get.return_value = MagicMock()
        with patch.object(pi_crud, "count_property_images", return_value=0):
            with patch.object(pi_crud, "unset_primary"):
                with patch.object(pi_crud, "get_next_order", return_value=0):
                    mock_db.add.return_value = None
                    mock_db.commit.return_value = None
                    mock_db.refresh.return_value = None
                    pi_crud.create(mock_db, obj_in=PropertyImageCreate(
                        property_id=10, image_url="https://x.com/a.jpg"))
        added = mock_db.add.call_args[0][0]
        assert added.is_primary is True

    def test_explicit_primary_unsets_others(self, pi_crud, mock_db):
        """is_primary=True → calls unset_primary."""
        mock_db.get.return_value = MagicMock()
        with patch.object(pi_crud, "count_property_images", return_value=2):
            with patch.object(pi_crud, "unset_primary") as mock_up:
                with patch.object(pi_crud, "get_next_order", return_value=2):
                    mock_db.add.return_value = None
                    mock_db.commit.return_value = None
                    mock_db.refresh.return_value = None
                    pi_crud.create(mock_db, obj_in=PropertyImageCreate(
                        property_id=10, image_url="https://x.com/b.jpg", is_primary=True))
        mock_up.assert_called_once_with(mock_db, property_id=10)

    def test_non_primary_no_unset(self, pi_crud, mock_db):
        """is_primary=False and not first → unset_primary NOT called."""
        mock_db.get.return_value = MagicMock()
        with patch.object(pi_crud, "count_property_images", return_value=2):
            with patch.object(pi_crud, "unset_primary") as mock_up:
                with patch.object(pi_crud, "get_next_order", return_value=2):
                    mock_db.add.return_value = None
                    mock_db.commit.return_value = None
                    mock_db.refresh.return_value = None
                    pi_crud.create(mock_db, obj_in=PropertyImageCreate(
                        property_id=10, image_url="https://x.com/c.jpg", is_primary=False))
        mock_up.assert_not_called()

    def test_logs_on_create(self, pi_crud, mock_db):
        mock_db.get.return_value = MagicMock()
        with patch.object(pi_crud, "count_property_images", return_value=1):
            with patch.object(pi_crud, "unset_primary"):
                with patch.object(pi_crud, "get_next_order", return_value=1):
                    mock_db.add.return_value = None
                    mock_db.commit.return_value = None
                    mock_db.refresh.return_value = None
                    with patch("app.crud.property_images.logger") as mock_log:
                        pi_crud.create(mock_db, obj_in=PropertyImageCreate(
                            property_id=10, image_url="https://x.com/d.jpg", is_primary=True))
        mock_log.info.assert_called_once()


# ─── update (lines 160-191) ──────────────────

class TestPIUpdate:
    def test_update_caption(self, pi_crud, mock_db):
        obj = make_image(caption="Old")
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        pi_crud.update(mock_db, db_obj=obj,
                       obj_in=PropertyImageUpdate(caption="New caption"))
        assert obj.caption == "New caption"

    def test_set_primary_calls_unset(self, pi_crud, mock_db):
        """Setting is_primary=True on non-primary → calls unset_primary."""
        obj = make_image(is_primary=False, property_id=10)
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        with patch.object(pi_crud, "unset_primary") as mock_up:
            pi_crud.update(mock_db, db_obj=obj,
                           obj_in=PropertyImageUpdate(is_primary=True))
        mock_up.assert_called_once_with(mock_db, property_id=10)

    def test_already_primary_no_unset(self, pi_crud, mock_db):
        """Already primary → unset_primary NOT called again."""
        obj = make_image(is_primary=True, property_id=10)
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        with patch.object(pi_crud, "unset_primary") as mock_up:
            pi_crud.update(mock_db, db_obj=obj,
                           obj_in=PropertyImageUpdate(is_primary=True))
        mock_up.assert_not_called()

    def test_strips_protected_fields(self, pi_crud, mock_db):
        obj = make_image(image_id=1, property_id=10)
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        pi_crud.update(mock_db, db_obj=obj,
                       obj_in=PropertyImageUpdate(caption="safe"))
        assert obj.image_id == 1
        assert obj.property_id == 10

    def test_logs_on_update(self, pi_crud, mock_db):
        obj = make_image()
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        with patch("app.crud.property_images.logger") as mock_log:
            pi_crud.update(mock_db, db_obj=obj,
                           obj_in=PropertyImageUpdate(caption="x"))
        mock_log.info.assert_called_once()


# ─── remove (lines 203-230) ──────────────────

class TestPIRemove:
    def test_not_found_raises(self, pi_crud, mock_db):
        with patch.object(pi_crud, "get", return_value=None):
            with pytest.raises(ValueError, match="Image with id"):
                pi_crud.remove(mock_db, image_id=999)

    def test_removes_non_primary(self, pi_crud, mock_db):
        """Non-primary deleted → no promotion needed."""
        obj = make_image(is_primary=False, property_id=10)
        with patch.object(pi_crud, "get", return_value=obj):
            with patch.object(pi_crud, "get_by_property", return_value=[]):
                mock_db.delete.return_value = None
                mock_db.commit.return_value = None
                pi_crud.remove(mock_db, image_id=1)
        mock_db.delete.assert_called_once_with(obj)

    def test_removes_primary_promotes_next(self, pi_crud, mock_db):
        """Primary deleted → first remaining promoted."""
        obj = make_image(is_primary=True, property_id=10)
        remaining = make_image(image_id=2, is_primary=False)
        with patch.object(pi_crud, "get", return_value=obj):
            with patch.object(pi_crud, "get_by_property", return_value=[remaining]):
                mock_db.delete.return_value = None
                mock_db.commit.return_value = None
                mock_db.add.return_value = None
                pi_crud.remove(mock_db, image_id=1)
        assert remaining.is_primary is True
        mock_db.add.assert_called_with(remaining)

    def test_removes_primary_no_remaining(self, pi_crud, mock_db):
        """Primary deleted, no remaining → no promotion."""
        obj = make_image(is_primary=True)
        with patch.object(pi_crud, "get", return_value=obj):
            with patch.object(pi_crud, "get_by_property", return_value=[]):
                mock_db.delete.return_value = None
                mock_db.commit.return_value = None
                pi_crud.remove(mock_db, image_id=1)
        # Second commit (for promotion) should not be called
        assert mock_db.commit.call_count == 1


# ─── get_next_order (lines 245-251) ──────────

class TestPIGetNextOrder:
    def test_returns_max_plus_one(self, pi_crud, mock_db):
        scalar(mock_db, 3)
        assert pi_crud.get_next_order(mock_db, property_id=10) == 4

    def test_returns_zero_when_no_images(self, pi_crud, mock_db):
        scalar(mock_db, None)
        assert pi_crud.get_next_order(mock_db, property_id=99) == 0


# ─── unset_primary (lines 264-276) ───────────

class TestPIUnsetPrimary:
    def test_executes_update(self, pi_crud, mock_db):
        mock_db.execute.return_value = None
        mock_db.commit.return_value = None
        pi_crud.unset_primary(mock_db, property_id=10)
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()


# ─── reorder (lines 291-307) ─────────────────

class TestPIReorder:
    def test_reorders_images(self, pi_crud, mock_db):
        img1 = make_image(image_id=1, display_order=0)
        img2 = make_image(image_id=2, display_order=1)
        with patch.object(pi_crud, "get_by_property", return_value=[img1, img2]):
            with patch.object(pi_crud, "get", side_effect=lambda db, image_id: {1: img1, 2: img2}[image_id]):
                mock_db.add.return_value = None
                mock_db.commit.return_value = None
                pi_crud.reorder(mock_db, property_id=10, image_order=[2, 1])
        assert img2.display_order == 0
        assert img1.display_order == 1

    def test_invalid_image_id_raises(self, pi_crud, mock_db):
        img1 = make_image(image_id=1)
        with patch.object(pi_crud, "get_by_property", return_value=[img1]):
            with pytest.raises(ValueError, match="does not belong to property"):
                pi_crud.reorder(mock_db, property_id=10, image_order=[99])

    def test_logs_reorder(self, pi_crud, mock_db):
        img1 = make_image(image_id=1)
        with patch.object(pi_crud, "get_by_property", return_value=[img1]):
            with patch.object(pi_crud, "get", return_value=img1):
                mock_db.add.return_value = None
                mock_db.commit.return_value = None
                with patch("app.crud.property_images.logger") as mock_log:
                    pi_crud.reorder(mock_db, property_id=10, image_order=[1])
        mock_log.info.assert_called_once()


# ─── singleton ────────────────────────────────

class TestPISingleton:
    def test_is_instance(self):
        assert isinstance(pi_singleton, PropertyImageCRUD)