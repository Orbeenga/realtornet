from fastapi.testclient import TestClient
from datetime import UTC, datetime, timedelta

from app.models.users import UserRole


class TestReadAgentsDirectory:

    def test_agents_directory_returns_agent_and_agency_owner_user_ids(
        self, client: TestClient, agency, agent_user, agency_owner_user
    ):
        response = client.get("/api/v1/agents/")

        assert response.status_code == 200
        data = response.json()
        user_ids = {item["user_id"] for item in data}
        assert agent_user.user_id in user_ids
        assert agency_owner_user.user_id in user_ids

        owner_item = next(item for item in data if item["user_id"] == agency_owner_user.user_id)
        assert owner_item["display_name"] == "Agency Owner"
        assert owner_item["agency_id"] == agency.agency_id
        assert owner_item["agency_name"] == agency.name

    def test_agents_directory_excludes_seekers(
        self, client: TestClient, normal_user
    ):
        response = client.get("/api/v1/agents/")

        assert response.status_code == 200
        assert normal_user.user_id not in {item["user_id"] for item in response.json()}
        assert normal_user.user_role == UserRole.SEEKER

    def test_agents_directory_includes_profile_id(
        self, client: TestClient
    ):
        response = client.get("/api/v1/agents/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        for item in data:
            assert "profile_id" in item

    def test_agents_directory_uses_latest_active_membership_for_agent_agency(
        self, client: TestClient, db, agency, other_agency, agent_user
    ):
        from app.models.agency_join_requests import AgencyAgentMembership

        db.add(
            AgencyAgentMembership(
                agency_id=agency.agency_id,
                user_id=agent_user.user_id,
                status="active",
            )
        )
        db.flush()
        db.add(
            AgencyAgentMembership(
                agency_id=other_agency.agency_id,
                user_id=agent_user.user_id,
                status="active",
                status_decided_at=datetime.now(UTC) + timedelta(minutes=1),
            )
        )
        db.flush()

        response = client.get("/api/v1/agents/")

        assert response.status_code == 200
        agent_item = next(item for item in response.json() if item["user_id"] == agent_user.user_id)
        assert agent_item["agency_id"] == other_agency.agency_id
        assert agent_item["agency_name"] == other_agency.name
