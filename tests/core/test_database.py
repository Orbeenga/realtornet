"""Tests for app.core.database — init_db, drop_db, get_db error paths."""
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from app.core.database import init_db, drop_db, get_db


class TestInitDb:
    def test_raises_in_non_testing(self):
        with patch("app.core.database.settings") as mock_settings:
            mock_settings.TESTING = False
            with pytest.raises(RuntimeError, match="init_db"):
                init_db()


class TestDropDb:
    def test_raises_in_non_testing(self):
        with patch("app.core.database.settings") as mock_settings:
            mock_settings.TESTING = False
            with pytest.raises(RuntimeError, match="drop_db"):
                drop_db()


class TestGetDb:
    def test_rollback_on_exception(self):
        """When the yielded session raises, get_db must rollback and close."""
        mock_session = MagicMock(spec=Session)
        with patch("app.core.database.SessionLocal", return_value=mock_session):
            gen = get_db()
            next(gen)
            exc = RuntimeError("boom")
            try:
                gen.throw(exc)
            except RuntimeError:
                pass
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()

    def test_commit_and_close_on_success(self):
        """When no exception occurs, get_db must commit and close."""
        mock_session = MagicMock(spec=Session)
        with patch("app.core.database.SessionLocal", return_value=mock_session):
            gen = get_db()
            next(gen)
            try:
                next(gen)
            except StopIteration:
                pass
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()
