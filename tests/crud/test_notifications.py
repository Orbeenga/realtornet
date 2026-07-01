"""Tests for app.crud.notifications — NotificationCRUD + fail-open."""
import pytest
from unittest.mock import MagicMock, patch

from app.crud.notifications import (
    create_notification_fail_open,
    NotificationCRUD,
    Notification,
)


class TestCreateNotificationFailOpen:
    """Fail-open must write normally and silently absorb DB errors."""

    def test_success_path_passes_through(self):
        """All args reach the Notification constructor and db.add/flush."""
        mock_db = MagicMock()
        mock_db.add.return_value = None
        mock_db.flush.return_value = None

        create_notification_fail_open(
            mock_db, user_id=1, event_type="test_event",
            listing_id=42, body_text="hello",
        )

        mock_db.add.assert_called_once()
        added = mock_db.add.call_args[0][0]
        assert isinstance(added, Notification)
        assert added.user_id == 1
        assert added.event_type == "test_event"
        assert added.body_text == "hello"

    def test_fail_open_on_db_error_does_not_propagate(self):
        """DB error must not propagate."""
        mock_db = MagicMock()
        mock_db.add.side_effect = RuntimeError("DB unreachable")
        # Should not raise
        create_notification_fail_open(
            mock_db, user_id=1, event_type="fail_test",
            listing_id=None, body_text="fail open",
        )
        # expunge should be called because obj was created before add failed
        mock_db.expunge.assert_called_once()

    def test_expunge_also_fails_gracefully(self):
        """If expunge also fails, nothing propagates."""
        mock_db = MagicMock()
        mock_db.add.side_effect = Exception("add fail")
        mock_db.expunge.side_effect = Exception("expunge fail")
        create_notification_fail_open(
            mock_db, user_id=1, event_type="double_fail",
            listing_id=42, body_text="nested fail",
        )


class TestNotificationCRUD:
    """Coverage for NotificationCRUD edge paths."""

    def test_mark_as_read_returns_none_for_missing(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = NotificationCRUD().mark_as_read(
            mock_db, notification_id=99999, user_id=1
        )
        assert result is None

    def test_create_notification_success(self):
        mock_db = MagicMock()
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        mock_db.refresh.return_value = None

        result = NotificationCRUD().create(
            mock_db, user_id=1, event_type="test",
            listing_id=None, body_text="hello",
        )
        assert isinstance(result, Notification)
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
        mock_db.refresh.assert_called_once()
