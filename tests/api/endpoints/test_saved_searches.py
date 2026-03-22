# tests/api/endpoints/test_saved_searches.py
"""
Surgical API-layer tests for /saved-searches endpoints.
"""
import uuid
from fastapi.testclient import TestClient

from app.api.endpoints import saved_searches as saved_searches_api
from app.core.security import generate_access_token, get_password_hash
from app.models.saved_searches import SavedSearch
from app.models.users import User, UserRole


class TestCreateSavedSearch:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.post(
            "/api/v1/saved-searches/",
            json={"search_params": {"min_price": 1000}, "name": "Test Search"}
        )
        assert response.status_code == 401

    def test_create_saved_search_success(
        self, client: TestClient, normal_user_token_headers, normal_user
    ):
        response = client.post(
            "/api/v1/saved-searches/",
            json={"search_params": {"min_price": 1000}, "name": "Test Search"},
            headers=normal_user_token_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == normal_user.user_id
        assert data["search_params"]["min_price"] == 1000


class TestReadUserSavedSearches:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.get("/api/v1/saved-searches/")
        assert response.status_code == 401

    def test_read_user_saved_searches_success(
        self, client: TestClient, normal_user_token_headers, db, normal_user
    ):
        saved = SavedSearch(
            user_id=normal_user.user_id,
            search_params={"min_price": 2000},
            name="My Search"
        )
        db.add(saved)
        db.flush()
        db.refresh(saved)

        response = client.get(
            "/api/v1/saved-searches/",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_pagination_params_accepted(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.get(
            "/api/v1/saved-searches/",
            params={"skip": 0, "limit": 5},
            headers=normal_user_token_headers
        )
        assert response.status_code == 200


class TestReadSavedSearch:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.get("/api/v1/saved-searches/1")
        assert response.status_code == 401

    def test_saved_search_not_found_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.get(
            "/api/v1/saved-searches/999999",
            headers=normal_user_token_headers
        )
        assert response.status_code == 404

    def test_forbidden_when_not_owner_returns_403(
        self, client: TestClient, db, normal_user
    ):
        saved = SavedSearch(
            user_id=normal_user.user_id,
            search_params={"min_price": 3000},
            name="Owner Search"
        )
        db.add(saved)
        db.flush()
        db.refresh(saved)

        other_user = User(
            email=f"other_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=get_password_hash("password"),
            first_name="Other",
            last_name="User",
            user_role=UserRole.SEEKER,
            supabase_id=uuid.uuid4(),
        )
        db.add(other_user)
        db.flush()
        db.refresh(other_user)

        other_token = generate_access_token(
            supabase_id=other_user.supabase_id,
            user_id=other_user.user_id,
            user_role=other_user.user_role.value,
        )
        other_headers = {"Authorization": f"Bearer {other_token}"}

        response = client.get(
            f"/api/v1/saved-searches/{saved.search_id}",
            headers=other_headers
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Not enough permissions to access this saved search"

    def test_read_saved_search_success(
        self, client: TestClient, normal_user_token_headers, db, normal_user
    ):
        saved = SavedSearch(
            user_id=normal_user.user_id,
            search_params={"min_price": 4000},
            name="Readable Search"
        )
        db.add(saved)
        db.flush()
        db.refresh(saved)

        response = client.get(
            f"/api/v1/saved-searches/{saved.search_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["search_id"] == saved.search_id


class TestUpdateSavedSearch:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.put(
            "/api/v1/saved-searches/1",
            json={"name": "Updated"}
        )
        assert response.status_code == 401

    def test_saved_search_not_found_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.put(
            "/api/v1/saved-searches/999999",
            json={"name": "Updated"},
            headers=normal_user_token_headers
        )
        assert response.status_code == 404

    def test_forbidden_when_not_owner_returns_403(
        self, client: TestClient, db, normal_user
    ):
        saved = SavedSearch(
            user_id=normal_user.user_id,
            search_params={"min_price": 5000},
            name="Owner Update"
        )
        db.add(saved)
        db.flush()
        db.refresh(saved)

        other_user = User(
            email=f"other_update_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=get_password_hash("password"),
            first_name="Other",
            last_name="User",
            user_role=UserRole.SEEKER,
            supabase_id=uuid.uuid4(),
        )
        db.add(other_user)
        db.flush()
        db.refresh(other_user)

        other_token = generate_access_token(
            supabase_id=other_user.supabase_id,
            user_id=other_user.user_id,
            user_role=other_user.user_role.value,
        )
        other_headers = {"Authorization": f"Bearer {other_token}"}

        response = client.put(
            f"/api/v1/saved-searches/{saved.search_id}",
            json={"name": "Not Allowed"},
            headers=other_headers
        )
        assert response.status_code == 403

    def test_update_saved_search_success(
        self, client: TestClient, normal_user_token_headers, db, normal_user
    ):
        saved = SavedSearch(
            user_id=normal_user.user_id,
            search_params={"min_price": 6000},
            name="Before Update"
        )
        db.add(saved)
        db.flush()
        db.refresh(saved)

        response = client.put(
            f"/api/v1/saved-searches/{saved.search_id}",
            json={"name": "After Update"},
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "After Update"


class TestDeleteSavedSearch:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.delete("/api/v1/saved-searches/1")
        assert response.status_code == 401

    def test_saved_search_not_found_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.delete(
            "/api/v1/saved-searches/999999",
            headers=normal_user_token_headers
        )
        assert response.status_code == 404

    def test_forbidden_when_not_owner_returns_403(
        self, client: TestClient, db, normal_user
    ):
        saved = SavedSearch(
            user_id=normal_user.user_id,
            search_params={"min_price": 7000},
            name="Owner Delete"
        )
        db.add(saved)
        db.flush()
        db.refresh(saved)

        other_user = User(
            email=f"other_delete_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=get_password_hash("password"),
            first_name="Other",
            last_name="User",
            user_role=UserRole.SEEKER,
            supabase_id=uuid.uuid4(),
        )
        db.add(other_user)
        db.flush()
        db.refresh(other_user)

        other_token = generate_access_token(
            supabase_id=other_user.supabase_id,
            user_id=other_user.user_id,
            user_role=other_user.user_role.value,
        )
        other_headers = {"Authorization": f"Bearer {other_token}"}

        response = client.delete(
            f"/api/v1/saved-searches/{saved.search_id}",
            headers=other_headers
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Not enough permissions to delete this saved search"

    def test_delete_saved_search_success(
        self, client: TestClient, normal_user_token_headers, db, normal_user
    ):
        saved = SavedSearch(
            user_id=normal_user.user_id,
            search_params={"min_price": 8000},
            name="Delete Me"
        )
        db.add(saved)
        db.flush()
        db.refresh(saved)

        response = client.delete(
            f"/api/v1/saved-searches/{saved.search_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_at"] is not None
        assert data["deleted_by"] is not None

    def test_soft_delete_returns_404_when_crud_returns_none(
        self, client: TestClient, normal_user_token_headers, db, normal_user, monkeypatch
    ):
        saved = SavedSearch(
            user_id=normal_user.user_id,
            search_params={"min_price": 9000},
            name="Delete None"
        )
        db.add(saved)
        db.flush()
        db.refresh(saved)

        monkeypatch.setattr(saved_searches_api.saved_search_crud, "soft_delete", lambda *args, **kwargs: None)
        response = client.delete(
            f"/api/v1/saved-searches/{saved.search_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 404


class TestExecuteSavedSearch:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.post("/api/v1/saved-searches/1/execute")
        assert response.status_code == 401

    def test_saved_search_not_found_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.post(
            "/api/v1/saved-searches/999999/execute",
            headers=normal_user_token_headers
        )
        assert response.status_code == 404

    def test_forbidden_when_not_owner_returns_403(
        self, client: TestClient, db, normal_user, monkeypatch
    ):
        saved = SavedSearch(
            user_id=normal_user.user_id,
            search_params={"min_price": 10000},
            name="Execute Owner"
        )
        db.add(saved)
        db.flush()
        db.refresh(saved)

        other_user = User(
            email=f"other_exec_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=get_password_hash("password"),
            first_name="Other",
            last_name="User",
            user_role=UserRole.SEEKER,
            supabase_id=uuid.uuid4(),
        )
        db.add(other_user)
        db.flush()
        db.refresh(other_user)

        other_token = generate_access_token(
            supabase_id=other_user.supabase_id,
            user_id=other_user.user_id,
            user_role=other_user.user_role.value,
        )
        other_headers = {"Authorization": f"Bearer {other_token}"}

        response = client.post(
            f"/api/v1/saved-searches/{saved.search_id}/execute",
            headers=other_headers
        )
        assert response.status_code == 403

    def test_execute_saved_search_success(
        self, client: TestClient, normal_user_token_headers, db, normal_user, monkeypatch
    ):
        saved = SavedSearch(
            user_id=normal_user.user_id,
            search_params={"min_price": 11000},
            name="Execute Me"
        )
        db.add(saved)
        db.flush()
        db.refresh(saved)

        monkeypatch.setattr(
            saved_searches_api.saved_search_crud,
            "execute_search",
            lambda *args, **kwargs: [{"property_id": 1}],
            raising=False
        )

        response = client.post(
            f"/api/v1/saved-searches/{saved.search_id}/execute",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
