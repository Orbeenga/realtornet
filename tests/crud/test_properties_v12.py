# tests/crud/test_properties_v12.py
"""
Targeted test for app/crud/properties.py line 960.
Ensures get_multi_by_params_approved enforces is_verified=True.
"""

from sqlalchemy.orm import Session

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
