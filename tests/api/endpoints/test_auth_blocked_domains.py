from starlette.testclient import TestClient

def test_register_blocked_smoke_domain_returns_400(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@smoke.realtornetapp.com",
            "password": "ValidPass123!",
            "first_name": "Smoke",
            "last_name": "User",
            "user_role": "seeker",
        },
    )
    assert response.status_code == 400
    assert "not permitted" in response.json()["detail"].lower()


def test_register_blocked_resend_domain_returns_400(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "delivered@resend.dev",
            "password": "ValidPass123!",
            "first_name": "Resend",
            "last_name": "Sink",
            "user_role": "seeker",
        },
    )
    assert response.status_code == 400
    assert "not permitted" in response.json()["detail"].lower()
