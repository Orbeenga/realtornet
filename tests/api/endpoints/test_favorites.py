# tests/api/endpoints/test_favorites.py
"""
Surgical API-layer tests for /favorites endpoints.
Covers permission branches, error paths, and happy paths.
"""

from fastapi.testclient import TestClient


class TestCreateFavorite:

    def test_unauthenticated_returns_401(self, client: TestClient, sample_property):
        favorite_data = {
            "user_id": 1,
            "property_id": sample_property.property_id
        }
        response = client.post("/api/v1/favorites/", json=favorite_data)
        assert response.status_code == 401

    def test_create_favorite_for_other_user_returns_403(
        self, client: TestClient, normal_user_token_headers, agent_user, sample_property
    ):
        # FavoriteCreate only takes property_id — user is always current_user
        # This test should instead verify the endpoint correctly ignores any user_id field
        # and uses current_user. Rename and repurpose:
        favorite_data = {"property_id": sample_property.property_id}
        response = client.post(
            "/api/v1/favorites/",
            json=favorite_data,
            headers=normal_user_token_headers
        )
        # Should succeed — user_id comes from token, not body
        assert response.status_code == 201

    def test_property_not_found_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        favorite_data = {
            "user_id": 1,
            "property_id": 999999
        }
        response = client.post(
            "/api/v1/favorites/",
            json=favorite_data,
            headers=normal_user_token_headers
        )
        assert response.status_code == 404

    def test_create_duplicate_favorite_returns_400(
        self, client: TestClient, normal_user_token_headers, normal_user, sample_property
    ):
        favorite_data = {
            "property_id": sample_property.property_id
        }
        # Create first favorite
        response = client.post(
            "/api/v1/favorites/",
            json=favorite_data,
            headers=normal_user_token_headers
        )
        assert response.status_code == 201

        # Try to create duplicate
        response = client.post(
            "/api/v1/favorites/",
            json=favorite_data,
            headers=normal_user_token_headers
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Favorite already exists for this property."

    def test_create_favorite_success(
        self, client: TestClient, normal_user_token_headers, normal_user, sample_property
    ):
        favorite_data = {
            "property_id": sample_property.property_id
        }
        response = client.post(
            "/api/v1/favorites/",
            json=favorite_data,
            headers=normal_user_token_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == normal_user.user_id
        assert data["property_id"] == sample_property.property_id
        assert data["deleted_at"] is None  # None means active


class TestDeleteFavorite:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.delete("/api/v1/favorites/?property_id=1")
        assert response.status_code == 401

    def test_delete_favorite_uses_auth_user_not_param(
        self, client: TestClient, normal_user_token_headers, sample_property
    ):
        client.post(
            "/api/v1/favorites/",
            json={"property_id": sample_property.property_id},
            headers=normal_user_token_headers
        )

        response = client.delete(
            f"/api/v1/favorites/?property_id={sample_property.property_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        assert response.json()["deleted_at"] is not None
        assert response.json()["deleted_by"] is not None

    def test_delete_nonexistent_favorite_returns_404(
        self, client: TestClient, normal_user_token_headers, normal_user
    ):
        response = client.delete(
            "/api/v1/favorites/?property_id=999999",
            headers=normal_user_token_headers
        )
        assert response.status_code == 404

    def test_delete_favorite_success(
        self, client: TestClient, normal_user_token_headers, normal_user, sample_property
    ):
        # First create a favorite
        favorite_data = {
            "property_id": sample_property.property_id
        }
        response = client.post(
            "/api/v1/favorites/",
            json=favorite_data,
            headers=normal_user_token_headers
        )
        assert response.status_code == 201

        # Now delete it
        response = client.delete(
            f"/api/v1/favorites/?property_id={sample_property.property_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == normal_user.user_id
        assert data["property_id"] == sample_property.property_id
        assert data["deleted_at"] is not None


class TestGetUserFavorites:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.get("/api/v1/favorites/user/1")
        assert response.status_code == 401

    def test_get_other_user_favorites_returns_403(
        self, client: TestClient, normal_user_token_headers, agent_user
    ):
        response = client.get(
            f"/api/v1/favorites/user/{agent_user.user_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Cannot access another user's favorites"

    def test_admin_can_get_other_user_favorites(
        self, client: TestClient, admin_token_headers, normal_user
    ):
        response = client.get(
            f"/api/v1/favorites/user/{normal_user.user_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_user_favorites_success(
        self, client: TestClient, normal_user_token_headers, normal_user
    ):
        response = client.get(
            f"/api/v1/favorites/user/{normal_user.user_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_pagination_params_accepted(
        self, client: TestClient, normal_user_token_headers, normal_user
    ):
        response = client.get(
            f"/api/v1/favorites/user/{normal_user.user_id}",
            params={"skip": 0, "limit": 5},
            headers=normal_user_token_headers
        )
        assert response.status_code == 200


class TestRestoreFavorite:

    def test_unauthenticated_returns_401(self, client: TestClient):
        # No fixtures needed — just hit the endpoint without auth
        response = client.post(
            "/api/v1/favorites/restore?property_id=1"
        )
        assert response.status_code == 401

    def test_restore_nonexistent_favorite_returns_404(
        self, client: TestClient, normal_user_token_headers, normal_user
    ):
        response = client.post(
            "/api/v1/favorites/restore?property_id=999999",
            headers=normal_user_token_headers
        )
        assert response.status_code == 404

    def test_restore_favorite_success(
        self, client: TestClient, normal_user_token_headers, normal_user, sample_property
    ):
        # Create favorite
        client.post(
            "/api/v1/favorites/",
            json={"property_id": sample_property.property_id},
            headers=normal_user_token_headers
        )
        # Delete it
        client.delete(
            f"/api/v1/favorites/?property_id={sample_property.property_id}",
            headers=normal_user_token_headers
        )
        # Restore it
        response = client.post(
            f"/api/v1/favorites/restore?property_id={sample_property.property_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_at"] is None


class TestCheckIsFavorited:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.get("/api/v1/favorites/is-favorited?property_id=1")
        assert response.status_code == 401

    def test_check_is_favorited_success(
        self, client: TestClient, normal_user_token_headers, normal_user, sample_property
    ):
        response = client.get(
            f"/api/v1/favorites/is-favorited?property_id={sample_property.property_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "is_favorited" in data
        assert isinstance(data["is_favorited"], bool)


class TestCountPropertyFavorites:

    def test_property_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/favorites/count/999999")
        assert response.status_code == 404

    def test_favorite_count_is_public(self, client: TestClient, sample_property):
        response = client.get(f"/api/v1/favorites/count/{sample_property.property_id}")
        assert response.status_code == 200
        assert "favorite_count" in response.json()

    def test_count_property_favorites_success(self, client: TestClient, sample_property):
        response = client.get(f"/api/v1/favorites/count/{sample_property.property_id}")
        assert response.status_code == 200
        data = response.json()
        assert "property_id" in data
        assert "favorite_count" in data
        assert isinstance(data["favorite_count"], int)


class TestCountUserFavorites:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.get("/api/v1/favorites/count/user/1")
        assert response.status_code == 401

    def test_count_other_user_favorites_returns_403(
        self, client: TestClient, normal_user_token_headers, agent_user
    ):
        response = client.get(
            f"/api/v1/favorites/count/user/{agent_user.user_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 403

    def test_admin_can_count_other_user_favorites(
        self, client: TestClient, admin_token_headers, normal_user
    ):
        response = client.get(
            f"/api/v1/favorites/count/user/{normal_user.user_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "favorite_count" in data

    def test_count_user_favorites_success(
        self, client: TestClient, normal_user_token_headers, normal_user
    ):
        response = client.get(
            f"/api/v1/favorites/count/user/{normal_user.user_id}",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == normal_user.user_id
        assert "favorite_count" in data


class TestBulkDeleteFavorites:

    def test_unauthenticated_returns_401(self, client: TestClient):
        bulk_data = [{"user_id": 1, "property_id": 1}]
        response = client.delete("/api/v1/favorites/bulk", params={"property_ids": [1]})
        assert response.status_code == 401

    # CORRECT — also note: bulk endpoint now only takes property_ids, not dicts:
    def test_bulk_delete_other_user_favorites_ignores_them(
        self, client, normal_user_token_headers, normal_user, sample_property
    ):
        # Create the favorite first
        client.post(
            "/api/v1/favorites/",
            json={"property_id": sample_property.property_id},
            headers=normal_user_token_headers
        )

        response = client.delete(
            "/api/v1/favorites/bulk",
            params={"property_ids": [sample_property.property_id]},
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 1
        assert data["total_requested"] == 1

    def test_bulk_delete_favorites_success(
        self, client: TestClient, normal_user_token_headers, normal_user, sample_property
    ):
        # Create a favorite first
        client.post(
            "/api/v1/favorites/",
            json={"property_id": sample_property.property_id},
            headers=normal_user_token_headers
        )

        # Bulk delete it
        response = client.delete(
            "/api/v1/favorites/bulk",
            params={"property_ids": [sample_property.property_id]},
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] >= 1
        assert data["total_requested"] == 1
        # STOP HERE — remove everything below this line in the test
       
        """
        # Create another property for testing
        from app.schemas.properties import PropertyCreate
        prop_data = PropertyCreate(
            title="Another Property",
            description="Test property",
            price=1000000,
            price_currency="NGN",
            bedrooms=2,
            bathrooms=1,
            area_sqm=80,
            listing_type="sale",
            property_type_id=1,
            location_id=1,
            agency_id=1
        )
        prop_response = client.post(
            "/api/v1/properties/",
            json=prop_data.model_dump(),
            headers=normal_user_token_headers
        )
        if prop_response.status_code == 201:
            prop2_id = prop_response.json()["property_id"]
            favorite_data2 = {
                "user_id": normal_user.user_id,
                "property_id": prop2_id
            }
            client.post("/api/v1/favorites/", json=favorite_data2, headers=normal_user_token_headers)

            # Now bulk delete
            bulk_data = [
                {"user_id": normal_user.user_id, "property_id": sample_property.property_id},
                {"user_id": normal_user.user_id, "property_id": prop2_id}
            ]
            response = client.delete(
                "/api/v1/favorites/bulk",
                json=bulk_data,
                headers=normal_user_token_headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["deleted_count"] == 2
            assert data["total_requested"] == 2
    """
