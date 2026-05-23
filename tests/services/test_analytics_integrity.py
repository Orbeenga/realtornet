"""Integrity summary must match non-zero detail rows."""

from unittest.mock import MagicMock

from app.services.analytics_services import AnalyticsService


class TestAnalyticsIntegritySummary:
    def test_summary_excludes_zero_count_issues(self):
        db = MagicMock()
        db.scalar.side_effect = [2, 0, 1]

        report = AnalyticsService().get_data_integrity_report(db)

        assert len(report.issues) == 2
        assert report.total_issues == 3
        assert report.high_severity_count == 3
        assert report.health_score == 97.0

    def test_summary_is_perfect_when_no_issues(self):
        db = MagicMock()
        db.scalar.side_effect = [0, 0, 0]

        report = AnalyticsService().get_data_integrity_report(db)

        assert report.issues == []
        assert report.total_issues == 0
        assert report.high_severity_count == 0
        assert report.health_score == 100.0
