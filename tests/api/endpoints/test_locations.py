# tests/api/endpoints/test_locations.py
"""
Surgical API-layer tests for /locations endpoints.
"""
from fastapi.testclient import TestClient
import pytest
from types import SimpleNamespace
from fastapi import HTTPException

from app.api.endpoints import locations as locations_api
from app.models.locations import Location


class TestReadLocations:

    def test_read_locations_public(self, client: TestClient):
        response = client.get("/api/v1/locations/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_filters_are_normalized(self, client: TestClient, monkeypatch):
        def _fake_get_by_filters(*args, **kwargs):
            assert kwargs["state"] == "lagos"
            assert kwargs["city"] == "ikeja"
            assert kwargs["neighborhood"] == "allen"
            return []

        monkeypatch.setattr(locations_api.location_crud, "get_by_filters", _fake_get_by_filters)
        response = client.get(
            "/api/v1/locations/",
            params={"state": " Lagos ", "city": " Ikeja ", "neighborhood": " Allen "}
        )
        assert response.status_code == 200


class TestCreateLocation:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.post("/api/v1/locations/", json={"state": "Lagos", "city": "Ikeja"})
        assert response.status_code == 401

    def test_invalid_latitude_returns_400(self, client: TestClient, admin_token_headers):
        response = client.post(
            "/api/v1/locations/",
            json={"state": "Lagos", "city": "Ikeja", "latitude": 200},
            headers=admin_token_headers
        )
        assert response.status_code == 422

    def test_invalid_longitude_returns_400(self, client: TestClient, admin_token_headers):
        response = client.post(
            "/api/v1/locations/",
            json={"state": "Lagos", "city": "Ikeja", "longitude": 200},
            headers=admin_token_headers
        )
        assert response.status_code == 422

    def test_invalid_latitude_returns_400_direct_call(self, db, admin_user):
        obj_in = SimpleNamespace(state="Lagos", city="Ikeja", latitude=200, longitude=None)
        with pytest.raises(HTTPException) as exc:
            locations_api.create_LocationResponse(
                db=db,
                location_in=obj_in,
                current_user=admin_user,
                _=None
            )
        assert exc.value.status_code == 400

    def test_invalid_longitude_returns_400_direct_call(self, db, admin_user):
        obj_in = SimpleNamespace(state="Lagos", city="Ikeja", latitude=None, longitude=200)
        with pytest.raises(HTTPException) as exc:
            locations_api.create_LocationResponse(
                db=db,
                location_in=obj_in,
                current_user=admin_user,
                _=None
            )
        assert exc.value.status_code == 400

    def test_create_location_success(self, client: TestClient, admin_token_headers):
        response = client.post(
            "/api/v1/locations/",
            json={"state": "Lagos", "city": "Ikeja"},
            headers=admin_token_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["state"].lower() == "lagos"
        assert data["city"].lower() == "ikeja"


class TestReadStatesCitiesNeighborhoods:

    def test_read_states_success(self, client: TestClient, monkeypatch):
        monkeypatch.setattr(locations_api.location_crud, "get_states", lambda *args, **kwargs: ["lagos"])
        response = client.get("/api/v1/locations/states")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_read_cities_normalizes_state(self, client: TestClient, monkeypatch):
        def _fake_get_cities(*args, **kwargs):
            assert kwargs["state"] == "lagos"
            return ["ikeja"]

        monkeypatch.setattr(locations_api.location_crud, "get_cities", _fake_get_cities)
        response = client.get("/api/v1/locations/cities", params={"state": " Lagos "})
        assert response.status_code == 200

    def test_read_neighborhoods_normalizes_state_city(self, client: TestClient, monkeypatch):
        def _fake_get_neighborhoods(*args, **kwargs):
            assert kwargs["state"] == "lagos"
            assert kwargs["city"] == "ikeja"
            return ["allen"]

        monkeypatch.setattr(locations_api.location_crud, "get_neighborhoods", _fake_get_neighborhoods)
        response = client.get(
            "/api/v1/locations/neighborhoods",
            params={"state": " Lagos ", "city": " Ikeja "}
        )
        assert response.status_code == 200


class TestReadLocationById:

    def test_location_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/locations/999999")
        assert response.status_code == 404

    def test_read_location_success(self, client: TestClient, db):
        loc = Location(state="Lagos", city="Ikeja")
        db.add(loc)
        db.flush()
        db.refresh(loc)

        response = client.get(f"/api/v1/locations/{loc.location_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["location_id"] == loc.location_id


class TestUpdateLocation:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.put("/api/v1/locations/1", json={"city": "Update"})
        assert response.status_code == 401

    def test_location_not_found_returns_404(self, client: TestClient, admin_token_headers):
        response = client.put(
            "/api/v1/locations/999999",
            json={"city": "Update"},
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_invalid_latitude_returns_400(self, client: TestClient, admin_token_headers, db):
        loc = Location(state="Lagos", city="Ikeja")
        db.add(loc)
        db.flush()
        db.refresh(loc)

        response = client.put(
            f"/api/v1/locations/{loc.location_id}",
            json={"latitude": 200},
            headers=admin_token_headers
        )
        assert response.status_code == 422

    def test_invalid_longitude_returns_400(self, client: TestClient, admin_token_headers, db):
        loc = Location(state="Lagos", city="Ikeja")
        db.add(loc)
        db.flush()
        db.refresh(loc)

        response = client.put(
            f"/api/v1/locations/{loc.location_id}",
            json={"longitude": 200},
            headers=admin_token_headers
        )
        assert response.status_code == 422

    def test_invalid_latitude_returns_400_direct_call(self, db, admin_user):
        loc = Location(state="Lagos", city="Ikeja")
        db.add(loc)
        db.flush()
        db.refresh(loc)

        obj_in = SimpleNamespace(latitude=200, longitude=None)
        with pytest.raises(HTTPException) as exc:
            locations_api.update_LocationResponse(
                db=db,
                location_id=loc.location_id,
                location_in=obj_in,
                current_user=admin_user,
                _=None
            )
        assert exc.value.status_code == 400

    def test_invalid_longitude_returns_400_direct_call(self, db, admin_user):
        loc = Location(state="Lagos", city="Ikeja")
        db.add(loc)
        db.flush()
        db.refresh(loc)

        obj_in = SimpleNamespace(latitude=None, longitude=200)
        with pytest.raises(HTTPException) as exc:
            locations_api.update_LocationResponse(
                db=db,
                location_id=loc.location_id,
                location_in=obj_in,
                current_user=admin_user,
                _=None
            )
        assert exc.value.status_code == 400

    def test_update_location_success(self, client: TestClient, admin_token_headers, db):
        loc = Location(state="Lagos", city="Ikeja")
        db.add(loc)
        db.flush()
        db.refresh(loc)

        response = client.put(
            f"/api/v1/locations/{loc.location_id}",
            json={"city": "Lekki"},
            headers=admin_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["city"].lower() == "lekki"


class TestDeleteLocation:

    def test_unauthenticated_returns_401(self, client: TestClient):
        response = client.delete("/api/v1/locations/1")
        assert response.status_code == 401

    def test_location_not_found_returns_404(self, client: TestClient, admin_token_headers):
        response = client.delete(
            "/api/v1/locations/999999",
            headers=admin_token_headers
        )
        assert response.status_code == 404

    def test_active_properties_prevent_delete_returns_400(
        self, client: TestClient, admin_token_headers, db, monkeypatch
    ):
        loc = Location(state="Lagos", city="Ikeja")
        db.add(loc)
        db.flush()
        db.refresh(loc)

        from app.crud.properties import property as property_crud
        monkeypatch.setattr(property_crud, "count_by_LocationResponse", lambda *args, **kwargs: 1, raising=False)

        response = client.delete(
            f"/api/v1/locations/{loc.location_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 400

    def test_delete_location_success(self, client: TestClient, admin_token_headers, db, monkeypatch):
        loc = Location(state="Lagos", city="Ikeja")
        db.add(loc)
        db.flush()
        db.refresh(loc)

        from app.crud.properties import property as property_crud
        monkeypatch.setattr(property_crud, "count_by_LocationResponse", lambda *args, **kwargs: 0, raising=False)

        response = client.delete(
            f"/api/v1/locations/{loc.location_id}",
            headers=admin_token_headers
        )
        assert response.status_code == 200


class TestReadLocationsByCoordinates:

    def test_read_by_coordinates_success(self, client: TestClient, monkeypatch):
        monkeypatch.setattr(
            locations_api.location_crud,
            "get_by_coordinates",
            lambda *args, **kwargs: []
        )
        response = client.get(
            "/api/v1/locations/by-coordinates/",
            params={"latitude": 6.5, "longitude": 3.4, "distance_km": 5}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
