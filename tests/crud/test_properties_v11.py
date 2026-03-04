# tests/crud/test_properties_v11.py
"""
Patch: single test covering properties.py line 64
    def get(self, db, property_id):
        if property_id is None:  ← line 64 (uncovered)
            return None
"""

import pytest
from unittest.mock import MagicMock
from sqlalchemy.orm import Session
from app.crud.properties import PropertyCRUD


@pytest.fixture
def crud():
    return PropertyCRUD()


@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)


class TestGetNoneGuard:
    def test_get_with_none_returns_none(self, crud, mock_db):
        """Line 64: property_id=None → returns None without hitting db.get()"""
        result = crud.get(mock_db, property_id=None)
        assert result is None
        mock_db.get.assert_not_called()