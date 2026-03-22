# tests/api/endpoints/test_reviews.py
"""
Surgical API-layer tests for /reviews endpoints.
Covers permission branches, validation branches, and success paths.
"""

from fastapi.testclient import TestClient

from app.models.reviews import Review


def _create_property_review(db, *, user_id: int, property_id: int, rating: int = 4, comment: str = "Good"):
    review = Review(
        user_id=user_id,
        property_id=property_id,
        agent_id=None,
        rating=rating,
        comment=comment,
    )
    db.add(review)
    db.flush()
    db.refresh(review)
    return review


def _create_agent_review(db, *, user_id: int, agent_id: int, rating: int = 4, comment: str = "Helpful"):
    review = Review(
        user_id=user_id,
        property_id=None,
        agent_id=agent_id,
        rating=rating,
        comment=comment,
    )
    db.add(review)
    db.flush()
    db.refresh(review)
    return review


class TestCreatePropertyReview:

    def test_unauthenticated_returns_401(self, client: TestClient, verified_property):
        response = client.post(
            "/api/v1/reviews/property/",
            json={"property_id": verified_property.property_id, "rating": 5, "comment": "Great"},
        )
        assert response.status_code == 401

    def test_property_not_found_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.post(
            "/api/v1/reviews/property/",
            json={"property_id": 999999, "rating": 5, "comment": "Great"},
            headers=normal_user_token_headers,
        )
        assert response.status_code == 404

    def test_duplicate_returns_400(
        self, client: TestClient, db, normal_user, normal_user_token_headers, verified_property
    ):
        _create_property_review(
            db,
            user_id=normal_user.user_id,
            property_id=verified_property.property_id,
        )
        response = client.post(
            "/api/v1/reviews/property/",
            json={"property_id": verified_property.property_id, "rating": 5, "comment": "Again"},
            headers=normal_user_token_headers,
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "You have already reviewed this property"

    def test_create_success_201(
        self, client: TestClient, normal_user_token_headers, verified_property
    ):
        response = client.post(
            "/api/v1/reviews/property/",
            json={"property_id": verified_property.property_id, "rating": 5, "comment": "Excellent"},
            headers=normal_user_token_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["property_id"] == verified_property.property_id
        assert data["rating"] == 5

    def test_invalid_rating_returns_422(
        self, client: TestClient, normal_user_token_headers, verified_property
    ):
        response = client.post(
            "/api/v1/reviews/property/",
            json={"property_id": verified_property.property_id, "rating": 6, "comment": "Too high"},
            headers=normal_user_token_headers,
        )
        assert response.status_code == 422


class TestReadPropertyReviews:

    def test_property_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/reviews/property/by-property/999999")
        assert response.status_code == 404

    def test_reviews_for_deleted_property_returns_404(
        self, client: TestClient, verified_property, admin_token_headers
    ):
        delete_response = client.delete(
            f"/api/v1/admin/properties/{verified_property.property_id}",
            headers=admin_token_headers,
        )
        assert delete_response.status_code == 200

        response = client.get(
            f"/api/v1/reviews/property/by-property/{verified_property.property_id}"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Property not found"

    def test_returns_reviews_for_property(
        self, client: TestClient, db, normal_user, verified_property
    ):
        _create_property_review(db, user_id=normal_user.user_id, property_id=verified_property.property_id)
        response = client.get(f"/api/v1/reviews/property/by-property/{verified_property.property_id}")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 1

    def test_skip_limit_applied(
        self, client: TestClient, db, normal_user, verified_property
    ):
        _create_property_review(db, user_id=normal_user.user_id, property_id=verified_property.property_id, comment="A")
        _create_property_review(db, user_id=normal_user.user_id, property_id=verified_property.property_id, comment="B")
        response = client.get(
            f"/api/v1/reviews/property/by-property/{verified_property.property_id}",
            params={"skip": 1, "limit": 1},
        )
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestReadPropertyReviewById:

    def test_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/reviews/property/999999")
        assert response.status_code == 404

    def test_returns_review(
        self, client: TestClient, db, normal_user, verified_property
    ):
        review = _create_property_review(db, user_id=normal_user.user_id, property_id=verified_property.property_id)
        response = client.get(f"/api/v1/reviews/property/{review.review_id}")
        assert response.status_code == 200
        assert response.json()["review_id"] == review.review_id


class TestUpdatePropertyReview:

    def test_unauthenticated_returns_401(
        self, client: TestClient, db, normal_user, verified_property
    ):
        review = _create_property_review(db, user_id=normal_user.user_id, property_id=verified_property.property_id)
        response = client.put(f"/api/v1/reviews/property/{review.review_id}", json={"rating": 3})
        assert response.status_code == 401

    def test_not_found_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.put(
            "/api/v1/reviews/property/999999",
            json={"rating": 3},
            headers=normal_user_token_headers,
        )
        assert response.status_code == 404

    def test_non_owner_non_admin_returns_403(
        self, client: TestClient, db, normal_user, owner_token_headers, verified_property
    ):
        review = _create_property_review(db, user_id=normal_user.user_id, property_id=verified_property.property_id)
        response = client.put(
            f"/api/v1/reviews/property/{review.review_id}",
            json={"rating": 2},
            headers=owner_token_headers,
        )
        assert response.status_code == 403

    def test_owner_updates_success(
        self, client: TestClient, db, normal_user, normal_user_token_headers, verified_property
    ):
        review = _create_property_review(db, user_id=normal_user.user_id, property_id=verified_property.property_id)
        response = client.put(
            f"/api/v1/reviews/property/{review.review_id}",
            json={"rating": 5, "comment": "Updated"},
            headers=normal_user_token_headers,
        )
        assert response.status_code == 200
        assert response.json()["rating"] == 5

    def test_admin_updates_success(
        self, client: TestClient, db, normal_user, admin_token_headers, verified_property
    ):
        review = _create_property_review(db, user_id=normal_user.user_id, property_id=verified_property.property_id)
        response = client.put(
            f"/api/v1/reviews/property/{review.review_id}",
            json={"rating": 4, "comment": "Admin update"},
            headers=admin_token_headers,
        )
        assert response.status_code == 200


class TestDeletePropertyReview:

    def test_unauthenticated_returns_401(
        self, client: TestClient, db, normal_user, verified_property
    ):
        review = _create_property_review(db, user_id=normal_user.user_id, property_id=verified_property.property_id)
        response = client.delete(f"/api/v1/reviews/property/{review.review_id}")
        assert response.status_code == 401

    def test_not_found_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.delete(
            "/api/v1/reviews/property/999999",
            headers=normal_user_token_headers,
        )
        assert response.status_code == 404

    def test_non_owner_non_admin_returns_403(
        self, client: TestClient, db, normal_user, owner_token_headers, verified_property
    ):
        review = _create_property_review(db, user_id=normal_user.user_id, property_id=verified_property.property_id)
        response = client.delete(
            f"/api/v1/reviews/property/{review.review_id}",
            headers=owner_token_headers,
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Not enough permissions to delete this ReviewResponse"

    def test_owner_soft_deletes_success(
        self, client: TestClient, db, normal_user, normal_user_token_headers, verified_property
    ):
        review = _create_property_review(db, user_id=normal_user.user_id, property_id=verified_property.property_id)
        response = client.delete(
            f"/api/v1/reviews/property/{review.review_id}",
            headers=normal_user_token_headers,
        )
        assert response.status_code == 200

    def test_admin_soft_deletes_success(
        self, client: TestClient, db, normal_user, admin_token_headers, verified_property
    ):
        review = _create_property_review(db, user_id=normal_user.user_id, property_id=verified_property.property_id)
        response = client.delete(
            f"/api/v1/reviews/property/{review.review_id}",
            headers=admin_token_headers,
        )
        assert response.status_code == 200
        assert response.json()["deleted_at"] is not None
        assert response.json()["deleted_by"] is not None


class TestCreateAgentReview:

    def test_unauthenticated_returns_401(self, client: TestClient, agent_user):
        response = client.post(
            "/api/v1/reviews/agent/",
            json={"agent_id": agent_user.user_id, "rating": 5, "comment": "Great service"},
        )
        assert response.status_code == 401

    def test_agent_not_found_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.post(
            "/api/v1/reviews/agent/",
            json={"agent_id": 999999, "rating": 5, "comment": "Great service"},
            headers=normal_user_token_headers,
        )
        assert response.status_code == 404

    def test_target_user_not_agent_returns_400(
        self, client: TestClient, normal_user_token_headers, normal_user
    ):
        response = client.post(
            "/api/v1/reviews/agent/",
            json={"agent_id": normal_user.user_id, "rating": 4, "comment": "Not agent"},
            headers=normal_user_token_headers,
        )
        assert response.status_code == 400

    def test_duplicate_returns_400(
        self, client: TestClient, db, normal_user, normal_user_token_headers, agent_user
    ):
        _create_agent_review(db, user_id=normal_user.user_id, agent_id=agent_user.user_id)
        response = client.post(
            "/api/v1/reviews/agent/",
            json={"agent_id": agent_user.user_id, "rating": 5, "comment": "Again"},
            headers=normal_user_token_headers,
        )
        assert response.status_code == 400

    def test_create_success_201(
        self, client: TestClient, normal_user_token_headers, agent_user
    ):
        response = client.post(
            "/api/v1/reviews/agent/",
            json={"agent_id": agent_user.user_id, "rating": 5, "comment": "Professional"},
            headers=normal_user_token_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["agent_id"] == agent_user.user_id


class TestReadAgentReviews:

    def test_agent_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/reviews/agent/by-agent/999999")
        assert response.status_code == 404

    def test_returns_reviews_for_agent(
        self, client: TestClient, db, normal_user, agent_user
    ):
        _create_agent_review(db, user_id=normal_user.user_id, agent_id=agent_user.user_id)
        response = client.get(f"/api/v1/reviews/agent/by-agent/{agent_user.user_id}")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 1


class TestReadAgentReviewById:

    def test_not_found_returns_404(self, client: TestClient):
        response = client.get("/api/v1/reviews/agent/999999")
        assert response.status_code == 404

    def test_returns_review(self, client: TestClient, db, normal_user, agent_user):
        review = _create_agent_review(db, user_id=normal_user.user_id, agent_id=agent_user.user_id)
        response = client.get(f"/api/v1/reviews/agent/{review.review_id}")
        assert response.status_code == 200
        assert response.json()["review_id"] == review.review_id


class TestUpdateAgentReview:

    def test_unauthenticated_returns_401(
        self, client: TestClient, db, normal_user, agent_user
    ):
        review = _create_agent_review(db, user_id=normal_user.user_id, agent_id=agent_user.user_id)
        response = client.put(f"/api/v1/reviews/agent/{review.review_id}", json={"rating": 4})
        assert response.status_code == 401

    def test_not_found_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.put(
            "/api/v1/reviews/agent/999999",
            json={"rating": 3},
            headers=normal_user_token_headers,
        )
        assert response.status_code == 404

    def test_non_owner_non_admin_returns_403(
        self, client: TestClient, db, normal_user, owner_token_headers, agent_user
    ):
        review = _create_agent_review(db, user_id=normal_user.user_id, agent_id=agent_user.user_id)
        response = client.put(
            f"/api/v1/reviews/agent/{review.review_id}",
            json={"rating": 2},
            headers=owner_token_headers,
        )
        assert response.status_code == 403

    def test_owner_updates_success(
        self, client: TestClient, db, normal_user, normal_user_token_headers, agent_user
    ):
        review = _create_agent_review(db, user_id=normal_user.user_id, agent_id=agent_user.user_id)
        response = client.put(
            f"/api/v1/reviews/agent/{review.review_id}",
            json={"rating": 5, "comment": "Updated"},
            headers=normal_user_token_headers,
        )
        assert response.status_code == 200
        assert response.json()["rating"] == 5

    def test_admin_updates_success(
        self, client: TestClient, db, normal_user, admin_token_headers, agent_user
    ):
        review = _create_agent_review(db, user_id=normal_user.user_id, agent_id=agent_user.user_id)
        response = client.put(
            f"/api/v1/reviews/agent/{review.review_id}",
            json={"rating": 4, "comment": "Admin edit"},
            headers=admin_token_headers,
        )
        assert response.status_code == 200


class TestDeleteAgentReview:

    def test_unauthenticated_returns_401(
        self, client: TestClient, db, normal_user, agent_user
    ):
        review = _create_agent_review(db, user_id=normal_user.user_id, agent_id=agent_user.user_id)
        response = client.delete(f"/api/v1/reviews/agent/{review.review_id}")
        assert response.status_code == 401

    def test_not_found_returns_404(
        self, client: TestClient, normal_user_token_headers
    ):
        response = client.delete(
            "/api/v1/reviews/agent/999999",
            headers=normal_user_token_headers,
        )
        assert response.status_code == 404

    def test_non_owner_non_admin_returns_403(
        self, client: TestClient, db, normal_user, owner_token_headers, agent_user
    ):
        review = _create_agent_review(db, user_id=normal_user.user_id, agent_id=agent_user.user_id)
        response = client.delete(
            f"/api/v1/reviews/agent/{review.review_id}",
            headers=owner_token_headers,
        )
        assert response.status_code == 403

    def test_owner_soft_deletes_success(
        self, client: TestClient, db, normal_user, normal_user_token_headers, agent_user
    ):
        review = _create_agent_review(db, user_id=normal_user.user_id, agent_id=agent_user.user_id)
        response = client.delete(
            f"/api/v1/reviews/agent/{review.review_id}",
            headers=normal_user_token_headers,
        )
        assert response.status_code == 200

    def test_admin_soft_deletes_success(
        self, client: TestClient, db, normal_user, admin_token_headers, agent_user
    ):
        review = _create_agent_review(db, user_id=normal_user.user_id, agent_id=agent_user.user_id)
        response = client.delete(
            f"/api/v1/reviews/agent/{review.review_id}",
            headers=admin_token_headers,
        )
        assert response.status_code == 200


class TestReadCurrentUserReviews:

    def test_read_user_property_reviews(
        self, client: TestClient, db, normal_user, normal_user_token_headers, verified_property
    ):
        _create_property_review(db, user_id=normal_user.user_id, property_id=verified_property.property_id)
        response = client.get(
            "/api/v1/reviews/by-user/property/",
            headers=normal_user_token_headers,
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1

    def test_read_user_agent_reviews(
        self, client: TestClient, db, normal_user, normal_user_token_headers, agent_user
    ):
        _create_agent_review(db, user_id=normal_user.user_id, agent_id=agent_user.user_id)
        response = client.get(
            "/api/v1/reviews/by-user/agent/",
            headers=normal_user_token_headers,
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1

