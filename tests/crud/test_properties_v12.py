# tests/crud/test_properties_v12.py
"""
Targeted test for app/crud/properties.py line 960.
Ensures get_multi_by_params_approved enforces is_verified=True.
"""

from sqlalchemy.orm import Session
import pytest
from fastapi import HTTPException

from app.crud.properties import property as property_crud


class TestGetMultiByParamsApproved:
    def test_only_verified_properties_returned(
        self, db: Session, verified_property, unverified_property
    ):
        """
        Public view must return only verified properties.

        This enforces the business rule that unverified listings are hidden.
        """
        results = property_crud.get_multi_by_params_approved(db, skip=0, limit=50)
        result_ids = [p.property_id for p in results]

        assert verified_property.property_id in result_ids
        assert unverified_property.property_id not in result_ids


def test_get_returns_none_for_soft_deleted_property(db, sample_property, normal_user):
    # get() must exclude soft-deleted properties after fix
    property_crud.soft_delete(
        db,
        property_id=sample_property.property_id,
        deleted_by_supabase_id=str(normal_user.supabase_id)
    )
    db.expire_all()
    result = property_crud.get(db, property_id=sample_property.property_id)
    assert result is None  # soft-deleted property must not be returned


def test_restore_soft_deleted_property_preserves_deleted_by(db, sample_property, normal_user):
    # restore() must work on deleted properties and preserve deleted_by audit field
    supabase_id = str(normal_user.supabase_id)
    property_crud.soft_delete(
        db,
        property_id=sample_property.property_id,
        deleted_by_supabase_id=supabase_id
    )
    db.expire_all()

    restored = property_crud.restore(
        db,
        property_id=sample_property.property_id,
        restored_by_supabase_id=supabase_id
    )
    assert restored is not None
    assert restored.deleted_at is None                    # restored
    assert str(restored.deleted_by) == supabase_id       # audit history preserved
    assert str(restored.updated_by) == supabase_id       # restorer recorded


def test_count_by_type_include_deleted_true_counts_soft_deleted(db, sample_property, property_type):
    initial_active = property_crud.count_by_type(
        db,
        property_type_id=property_type.property_type_id
    )
    assert initial_active >= 1

    property_crud.soft_delete(
        db,
        property_id=sample_property.property_id,
        deleted_by_supabase_id="550e8400-e29b-41d4-a716-446655440001"
    )

    active_after_delete = property_crud.count_by_type(
        db,
        property_type_id=property_type.property_type_id
    )
    all_after_delete = property_crud.count_by_type(
        db,
        property_type_id=property_type.property_type_id,
        include_deleted=True
    )

    assert active_after_delete == 0
    assert all_after_delete >= 1


def test_count_by_location_counts_only_active(db, sample_property, location):
    initial_active = property_crud.count_by_location(
        db,
        location_id=location.location_id
    )
    assert initial_active >= 1

    property_crud.soft_delete(
        db,
        property_id=sample_property.property_id,
        deleted_by_supabase_id="550e8400-e29b-41d4-a716-446655440001"
    )

    active_after_delete = property_crud.count_by_location(
        db,
        location_id=location.location_id
    )
    assert active_after_delete == 0


def test_verify_property_idempotent_updates_actor(db, verified_property):
    updated = property_crud.verify_property(
        db,
        property_id=verified_property.property_id,
        is_verified=True,
        updated_by="550e8400-e29b-41d4-a716-446655440001"
    )
    assert updated is not None
    assert str(updated.updated_by) == "550e8400-e29b-41d4-a716-446655440001"


def test_soft_delete_requires_deleted_by(db, sample_property):
    with pytest.raises(HTTPException) as exc:
        property_crud.soft_delete(
            db,
            property_id=sample_property.property_id
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "deleted_by_supabase_id is required"
