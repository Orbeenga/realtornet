"""
Surgical API-layer tests for app/api/endpoints/analytics.py.

Analytics endpoints are sensitive and must require authentication.
Admin analytics endpoints must enforce admin-only access.
"""
import uuid
from types import SimpleNamespace
from fastapi.testclient import TestClient

from app.crud.agent_profiles import agent_profile as agent_profile_crud
from app.models.analytics import AgentPerformanceView
from app.schemas.agent_profiles import AgentProfileCreate
from app.services.analytics_services import analytics_service


def _ensure_agent_profile(db, agent_user, agency):
    """Create an agent profile if one does not already exist."""
    existing = agent_profile_crud.get_by_user_id(db, user_id=agent_user.user_id)
    if existing:
        return existing
    profile = agent_profile_crud.create(
        db,
        obj_in=AgentProfileCreate(
            user_id=agent_user.user_id,
            agency_id=agency.agency_id,
            license_number=f"LIC-{uuid.uuid4().hex[:8]}",
            years_experience=3
        ),
        created_by=agent_user.supabase_id
    )
    # Ensure view-backed queries see the new row in this transaction.
    db.flush()
    db.expire_all()
    return profile


class TestAnalyticsActiveProperties:
    def test_get_active_properties_returns_list(
        self, client: TestClient, normal_user_token_headers
    ):
        """
        Authenticated users can fetch active properties.

        This validates that analytics data is protected by auth and
        returns a list structure even when empty.
        """
        response = client.get(
            "/api/v1/analytics/properties/active",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_active_properties_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Unauthenticated users must not access analytics data.

        This prevents public scraping of property listings.
        """
        response = client.get("/api/v1/analytics/properties/active")
        assert response.status_code == 401

    def test_get_active_properties_error_returns_500(
        self, client: TestClient, normal_user_token_headers, monkeypatch
    ):
        """
        Service failures must return 500 for active properties.

        This exercises the exception handling branch.
        """
        def boom(*args, **kwargs):
            raise Exception("boom")

        monkeypatch.setattr(analytics_service, "get_active_properties_by_location", boom)
        response = client.get(
            "/api/v1/analytics/properties/active?state=Lagos",
            headers=normal_user_token_headers
        )
        assert response.status_code == 500


class TestAnalyticsFeaturedProperties:
    def test_get_featured_properties_returns_list(
        self, client: TestClient, normal_user_token_headers
    ):
        """
        Authenticated users can fetch featured properties.

        This ensures sensitive featured inventory is not public.
        """
        response = client.get(
            "/api/v1/analytics/properties/featured",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_featured_properties_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Unauthenticated access must be blocked.

        Featured inventory is commercially sensitive.
        """
        response = client.get("/api/v1/analytics/properties/featured")
        assert response.status_code == 401

    def test_get_featured_properties_error_returns_500(
        self, client: TestClient, normal_user_token_headers, monkeypatch
    ):
        """
        Service failures must return 500 for featured properties.
        """
        def boom(*args, **kwargs):
            raise Exception("boom")

        monkeypatch.setattr(analytics_service, "get_featured_properties", boom)
        response = client.get(
            "/api/v1/analytics/properties/featured",
            headers=normal_user_token_headers
        )
        assert response.status_code == 500


class TestAnalyticsAgentPerformance:
    def test_get_agent_performance_list_returns_list(
        self, client: TestClient, normal_user_token_headers, db, agent_user, agency
    ):
        """
        Authenticated users can fetch agent performance list.

        This validates the view-backed list is gated by auth.
        """
        _ensure_agent_profile(db, agent_user, agency)
        response = client.get(
            "/api/v1/analytics/agents/performance",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_agent_performance_list_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Unauthenticated requests must be rejected.

        Agent metrics must not be public.
        """
        response = client.get("/api/v1/analytics/agents/performance")
        assert response.status_code == 401

    def test_get_agent_performance_list_error_returns_500(
        self, client: TestClient, normal_user_token_headers, monkeypatch
    ):
        """
        Service failures must return 500 for agent performance list.
        """
        def boom(*args, **kwargs):
            raise Exception("boom")

        monkeypatch.setattr(analytics_service, "get_agent_performance_list", boom)
        response = client.get(
            "/api/v1/analytics/agents/performance",
            headers=normal_user_token_headers
        )
        assert response.status_code == 500


class TestAnalyticsAgentPerformanceById:
    def test_get_agent_performance_by_id_returns_agent(
        self, client: TestClient, normal_user_token_headers, db, agent_user, agency
    ):
        """
        Authenticated users can fetch a specific agent's performance.

        Ensures the agent view is readable once authenticated.
        """
        _ensure_agent_profile(db, agent_user, agency)
        view_row = (
            db.query(AgentPerformanceView)
            .filter(AgentPerformanceView.user_id == agent_user.user_id)
            .first()
        )
        response = client.get(
            f"/api/v1/analytics/agents/{agent_user.user_id}",
            headers=normal_user_token_headers
        )
        if view_row is None:
            # If the view isn't populated in this DB, endpoint should 404.
            assert response.status_code == 404
            return
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == agent_user.user_id

    def test_get_agent_performance_by_id_not_found_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        """
        Nonexistent agent IDs must return 404.

        This avoids misleading success responses.
        """
        response = client.get(
            "/api/v1/analytics/agents/999999",
            headers=normal_user_token_headers
        )
        assert response.status_code == 404

    def test_get_agent_performance_by_id_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Unauthenticated access to agent metrics must be blocked.

        Prevents public scraping of agent performance.
        """
        response = client.get("/api/v1/analytics/agents/1")
        assert response.status_code == 401

    def test_get_agent_performance_by_id_success_branch(
        self, client: TestClient, normal_user_token_headers, monkeypatch
    ):
        """
        Successful agent lookups should return the agent payload.
        """
        dummy = SimpleNamespace(
            user_id=123,
            agent_name="Test Agent",
            license_number="LIC-123",
            agency_name="Test Agency",
            total_listings=1,
            active_listings=1,
            sold_count=0,
            avg_rating=None,
            review_count=0
        )
        monkeypatch.setattr(analytics_service, "get_agent_performance_by_id", lambda *args, **kwargs: dummy)
        response = client.get(
            "/api/v1/analytics/agents/123",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        assert response.json()["user_id"] == 123


class TestAnalyticsTopAgents:
    def test_get_top_agents_returns_list(
        self, client: TestClient, normal_user_token_headers, db, agent_user, agency
    ):
        """
        Authenticated users can fetch top agents list.

        Validates leaderboard access is authenticated.
        """
        _ensure_agent_profile(db, agent_user, agency)
        response = client.get(
            "/api/v1/analytics/agents/top",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_top_agents_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Unauthenticated access must be rejected.

        Top agent rankings are sensitive business data.
        """
        response = client.get("/api/v1/analytics/agents/top")
        assert response.status_code == 401

    def test_get_top_agents_error_returns_500(
        self, client: TestClient, normal_user_token_headers, monkeypatch
    ):
        """
        Service failures must return 500 for top agents.
        """
        def boom(*args, **kwargs):
            raise Exception("boom")

        monkeypatch.setattr(analytics_service, "get_top_agents", boom)
        response = client.get(
            "/api/v1/analytics/agents/top",
            headers=normal_user_token_headers
        )
        assert response.status_code == 500


class TestAnalyticsPropertyEngagement:
    def test_get_property_engagement_returns_metrics(
        self, client: TestClient, normal_user_token_headers, unverified_property_owned_by_agent
    ):
        """
        Authenticated users can fetch engagement metrics for a property.

        Ensures analytics response includes key engagement fields.
        """
        response = client.get(
            f"/api/v1/analytics/properties/{unverified_property_owned_by_agent.property_id}/engagement",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["property_id"] == unverified_property_owned_by_agent.property_id
        assert "inquiry_count" in data
        assert "favorite_count" in data
        assert "review_count" in data

    def test_get_property_engagement_not_found_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        """
        Nonexistent property IDs must return 404.

        Prevents misleading analytics responses.
        """
        response = client.get(
            "/api/v1/analytics/properties/999999/engagement",
            headers=normal_user_token_headers
        )
        assert response.status_code == 404

    def test_get_property_engagement_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Unauthenticated access must be rejected.

        Engagement metrics are sensitive platform data.
        """
        response = client.get("/api/v1/analytics/properties/1/engagement")
        assert response.status_code == 401


class TestAnalyticsSystemStats:
    def test_admin_gets_system_stats(
        self, client: TestClient, admin_token_headers
    ):
        """
        Admins can access system statistics.

        This validates admin-only visibility into platform health.
        """
        response = client.get(
            "/api/v1/analytics/system/stats",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert "properties" in data
        assert "inquiries" in data

    def test_system_stats_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers
    ):
        """
        Non-admins must not access system stats.

        These aggregates are sensitive operational metrics.
        """
        response = client.get(
            "/api/v1/analytics/system/stats",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_system_stats_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Unauthenticated requests must be rejected.

        Ensures admin endpoints are fully protected.
        """
        response = client.get("/api/v1/analytics/system/stats")
        assert response.status_code == 401

    def test_system_stats_error_returns_500(
        self, client: TestClient, admin_token_headers, monkeypatch
    ):
        """
        Service failures must return 500 for system stats.
        """
        def boom(*args, **kwargs):
            raise Exception("boom")

        monkeypatch.setattr(analytics_service, "get_system_stats", boom)
        response = client.get(
            "/api/v1/analytics/system/stats",
            headers=admin_token_headers
        )
        assert response.status_code == 500


class TestAnalyticsSystemUsage:
    def test_admin_gets_usage_metrics(
        self, client: TestClient, admin_token_headers
    ):
        """
        Admins can access usage metrics.

        Validates operational visibility into platform activity.
        """
        response = client.get(
            "/api/v1/analytics/system/usage",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "user_logins" in data
        assert "new_properties" in data
        assert "new_inquiries" in data
        assert "new_users" in data

    def test_system_usage_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers
    ):
        """
        Non-admins must not access usage metrics.

        Usage metrics are admin-only observability signals.
        """
        response = client.get(
            "/api/v1/analytics/system/usage",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_system_usage_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Unauthenticated requests must be rejected.

        Admin analytics must not be publicly accessible.
        """
        response = client.get("/api/v1/analytics/system/usage")
        assert response.status_code == 401

    def test_system_usage_error_returns_500(
        self, client: TestClient, admin_token_headers, monkeypatch
    ):
        """
        Service failures must return 500 for usage metrics.
        """
        def boom(*args, **kwargs):
            raise Exception("boom")

        monkeypatch.setattr(analytics_service, "get_usage_metrics", boom)
        response = client.get(
            "/api/v1/analytics/system/usage",
            headers=admin_token_headers
        )
        assert response.status_code == 500


class TestAnalyticsSystemIntegrity:
    def test_admin_gets_integrity_report(
        self, client: TestClient, admin_token_headers
    ):
        """
        Admins can access data integrity reports.

        Validates audit and data-quality visibility.
        """
        response = client.get(
            "/api/v1/analytics/system/integrity",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "issues" in data
        assert "total_issues" in data
        assert "health_score" in data

    def test_system_integrity_non_admin_returns_403(
        self, client: TestClient, normal_user_token_headers
    ):
        """
        Non-admins must not access integrity reports.

        Integrity diagnostics are privileged platform insights.
        """
        response = client.get(
            "/api/v1/analytics/system/integrity",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_system_integrity_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Unauthenticated requests must be rejected.

        Prevents public access to internal health diagnostics.
        """
        response = client.get("/api/v1/analytics/system/integrity")
        assert response.status_code == 401

    def test_system_integrity_error_returns_500(
        self, client: TestClient, admin_token_headers, monkeypatch
    ):
        """
        Service failures must return 500 for integrity report.
        """
        def boom(*args, **kwargs):
            raise Exception("boom")

        monkeypatch.setattr(analytics_service, "get_data_integrity_report", boom)
        response = client.get(
            "/api/v1/analytics/system/integrity",
            headers=admin_token_headers
        )
        assert response.status_code == 500
