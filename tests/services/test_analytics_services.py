# tests/services/test_analytics_services.py
"""
Targeted tests for analytics service branches.
Focus: location filters and order_by branches.
"""

from unittest.mock import MagicMock

from app.services.analytics_services import AnalyticsService
from app.models.analytics import ActivePropertiesView, AgentPerformanceView


class TestAnalyticsServiceLocationFilters:
    def test_get_active_properties_by_location_applies_filters(self):
        """
        State and city filters should be applied before pagination.
        """
        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query
        query.filter.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query
        query.all.return_value = []

        service = AnalyticsService()
        result = service.get_active_properties_by_location(
            db, state="Lagos", city="Lekki", skip=5, limit=10
        )

        assert result == []
        assert query.filter.call_count == 2
        query.offset.assert_called_once_with(5)
        query.limit.assert_called_once_with(10)


class TestAnalyticsServiceTopAgentsOrdering:
    def test_get_top_agents_orders_by_active_listings(self):
        """
        Order by active_listings should call the correct order_by clause.
        """
        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.all.return_value = []

        service = AnalyticsService()
        service.get_top_agents(db, limit=5, order_by="active_listings")

        assert query.order_by.called
        assert query.limit.called

    def test_get_top_agents_orders_by_sold_count(self):
        """
        Order by sold_count should call the correct order_by clause.
        """
        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.all.return_value = []

        service = AnalyticsService()
        service.get_top_agents(db, limit=5, order_by="sold_count")

        assert query.order_by.called
        assert query.limit.called

    def test_get_top_agents_orders_by_avg_rating(self):
        """
        Order by avg_rating should call the correct order_by clause.
        """
        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.all.return_value = []

        service = AnalyticsService()
        service.get_top_agents(db, limit=5, order_by="avg_rating")

        assert query.order_by.called
        assert query.limit.called
