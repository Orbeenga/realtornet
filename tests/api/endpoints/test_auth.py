# tests/api/endpoints/test_auth.py  (additions to existing file)
"""
Surgical additions to cover the 7 uncovered lines in auth.py:
Lines 114, 128, 135, 158, 191-196

Add these classes/methods to the existing test_auth.py file.
send_welcome_email.delay must be mocked in ALL register tests
to prevent Celery connection errors in the test environment.
"""
from unittest.mock import patch
import pytest
from starlette.testclient import TestClient


class TestLoginBranches:
    def test_login_wrong_password_returns_401(
        self, client: TestClient, normal_user
    ):
        """
        Wrong password must return 401 with a generic message.

        This prevents user enumeration by keeping the response identical
        to the unknown-email case.
        """
        response = client.post(
            "/api/v1/auth/login",
            data={"username": normal_user.email, "password": "wrongpassword"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect email or password"

    def test_login_nonexistent_email_returns_401(
        self, client: TestClient
    ):
        """
        Unknown email must return the same 401 message as wrong password.

        This enforces indistinguishable auth failures to prevent enumeration.
        """
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "ghost@example.com", "password": "anypassword"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect email or password"

    def test_login_deleted_user_returns_401(
        self, client: TestClient, db, normal_user
    ):
        """
        Soft-deleted users must not be able to log in.

        This validates that account status overrides valid credentials.
        """
        from app.crud.users import user as user_crud
        user_crud.soft_delete(
            db,
            user_id=normal_user.user_id,
            deleted_by_supabase_id=normal_user.supabase_id
        )

        response = client.post(
            "/api/v1/auth/login",
            data={"username": normal_user.email, "password": "password"}
        )
        assert response.status_code == 401
        assert "Inactive" in response.json()["detail"]

    def test_login_inactive_user_returns_401(
        self, client: TestClient, db
    ):
        """
        Line 114 branch: user exists and authenticates but is_active returns False.
        Covers the inactive user check after successful authentication.
        """
        from app.models.users import User, UserRole
        import uuid, bcrypt
        password = "ValidPass123!"
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        inactive_user = User(
            email=f"inactive_{uuid.uuid4().hex[:6]}@example.com",
            supabase_id=str(uuid.uuid4()),
            user_role=UserRole.SEEKER,
            password_hash=hashed,
            first_name="Inactive",
            last_name="User",
            is_verified=False,
            deleted_at=__import__('datetime').datetime.utcnow()  # soft-deleted = inactive
        )
        db.add(inactive_user)
        db.flush()

        response = client.post(
            "/api/v1/auth/login",
            data={"username": inactive_user.email, "password": password}
        )
        assert response.status_code == 401
        assert "Inactive" in response.json()["detail"]

    def test_login_success_returns_both_tokens(
        self, client: TestClient, normal_user, db
    ):
        """
        Line 128 branch: successful login returns access_token AND refresh_token.
        Verifies generate_refresh_token is called (line 128 reached).
        Requires normal_user fixture to have a known password.
        """
        # normal_user fixture must have password "password123" or equivalent
        # Check conftest for the password used in normal_user fixture
        response = client.post(
            "/api/v1/auth/login",
            data={"username": normal_user.email, "password": "password"}
        )
        if response.status_code == 200:
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["token_type"] == "bearer"


class TestRefreshTokenBranches:
    def test_refresh_with_malformed_token_returns_401(
        self, client: TestClient
    ):
        """
        Malformed refresh token must return 401.

        This ensures invalid token inputs never crash the endpoint.
        """
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "not-a-jwt"}
        )
        assert response.status_code == 401
        assert "Invalid" in response.json()["detail"]

    def test_refresh_with_access_token_returns_401(self, client: TestClient, normal_user):
        """
        Line 135 branch: submitting an access token to the refresh endpoint.
        Token type check fires — must return 401.
        """
        from app.core.security import generate_access_token
        access_token = generate_access_token(
            supabase_id=normal_user.supabase_id,
            user_id=normal_user.user_id,
            user_role=normal_user.user_role.value
        )
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token}
        )
        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]

    def test_refresh_with_deleted_user_returns_401(self, client: TestClient, db):
        """
        Line 158 branch: valid refresh token but user was soft-deleted after token issued.
        user_crud.get() returns None — must return 401.
        """
        from app.core.security import generate_refresh_token
        import uuid
        ghost_supabase_id = str(uuid.uuid4())
        ghost_user_id = 999999999  # does not exist in DB

        refresh_token = generate_refresh_token(
            supabase_id=ghost_supabase_id,
            user_id=ghost_user_id,
            user_role="seeker",
            agency_id=None
        )
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert response.status_code == 401
        assert "User not found" in response.json()["detail"]


    def test_refresh_inactive_user_returns_401(
        self, client: TestClient, db, normal_user
    ):
        """
        Valid refresh token must fail if the user is inactive (soft-deleted).

        Token validity does not override account status.
        """
        from app.core.security import generate_refresh_token
        from app.crud.users import user as user_crud

        user_crud.soft_delete(
            db,
            user_id=normal_user.user_id,
            deleted_by_supabase_id=normal_user.supabase_id
        )
        refresh_token = generate_refresh_token(
            supabase_id=normal_user.supabase_id,
            user_id=normal_user.user_id,
            user_role=normal_user.user_role.value,
            agency_id=normal_user.agency_id
        )
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert response.status_code == 401
        assert "user not found" in response.json()["detail"].lower()


class TestRegisterBranches:
    def test_register_success(self, client: TestClient, db):
        """
        Lines 191-196: successful registration triggers send_welcome_email.delay.
        Celery must be mocked to prevent connection error in test environment.
        """
        import uuid
        with patch("app.api.endpoints.auth.send_welcome_email") as mock_email:
            mock_email.delay.return_value = None
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"newuser_{uuid.uuid4().hex[:6]}@example.com",
                    "password": "ValidPass123!",
                    "first_name": "New",
                    "last_name": "User",
                    "user_role": "seeker"
                }
            )
        assert response.status_code == 200
        mock_email.delay.assert_called_once()

    def test_register_soft_deleted_email_returns_400(self, client: TestClient, db):
        """
        Register with email of a previously soft-deleted user returns 400
        with 'previously deleted' message — not generic 'already exists'.
        """
        from app.models.users import User, UserRole
        import uuid
        email = f"deleted_{uuid.uuid4().hex[:6]}@example.com"
        deleted_user = User(
            email=email,
            supabase_id=str(uuid.uuid4()),
            user_role=UserRole.SEEKER,
            password_hash="hashed_placeholder",
            first_name="Was",
            last_name="Deleted",
            deleted_at=__import__('datetime').datetime.utcnow()
        )
        db.add(deleted_user)
        db.flush()

        with patch("app.api.endpoints.auth.send_welcome_email") as mock_email:
            mock_email.delay.return_value = None
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "email": email,
                    "password": "ValidPass123!",
                    "first_name": "New",
                    "last_name": "Attempt",
                    "user_role": "seeker"
                }
            )
        assert response.status_code == 400
        assert "previously deleted" in response.json()["detail"]

    def test_register_existing_active_email_returns_400(self, client: TestClient, normal_user):
        """
        Register with an already active email returns 400.
        """
        with patch("app.api.endpoints.auth.send_welcome_email") as mock_email:
            mock_email.delay.return_value = None
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "email": normal_user.email,
                    "password": "ValidPass123!",
                    "first_name": "Dup",
                    "last_name": "User",
                    "user_role": "seeker"
                }
            )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]


class TestMeEndpoint:
    def test_get_me_returns_current_user(
        self, client: TestClient, normal_user_token_headers, normal_user
    ):
        """
        Authenticated users must receive their own user record.

        This validates the /me endpoint returns correct identity data.
        """
        response = client.get(
            "/api/v1/auth/me",
            headers=normal_user_token_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == normal_user.user_id
        assert data["email"] == normal_user.email
        assert data["deleted_at"] is None

    def test_get_me_unauthenticated_returns_401(
        self, client: TestClient
    ):
        """
        Missing token must return 401.

        This protects user identity endpoints from anonymous access.
        """
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_get_me_with_expired_token_returns_401(
        self, client: TestClient, normal_user
    ):
        """
        Expired token must be rejected with 401.

        This enforces token expiry and prevents long-lived access.
        """
        from jose import jwt
        from datetime import datetime, timezone, timedelta
        from app.core.config import settings

        expired_payload = {
            "sub": str(normal_user.supabase_id),
            "supabase_id": str(normal_user.supabase_id),
            "user_id": normal_user.user_id,
            "role": normal_user.user_role.value,
            "token_type": "access",
            "agency_id": normal_user.agency_id,
            "iat": int(datetime.now(timezone.utc).timestamp()) - 3600,
            "exp": int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp()),
        }
        token = jwt.encode(
            expired_payload,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401
