# tests/core/test_security.py
"""
Targeted tests for app/core/security.py.
Focus: token decode error paths and refresh validation.
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from jose import jwt

from app.core import security
from app.core.config import settings
from app.core.exceptions import AuthenticationException


class TestPasswordHashing:
    def test_verify_password_with_invalid_hash_returns_false(self):
        """
        Invalid bcrypt hashes must return False, not crash.

        This protects login flow from malformed stored hashes.
        """
        assert security.verify_password("password", "not-a-valid-hash") is False


class TestDecodeToken:
    def test_decode_token_expired_raises(self):
        """
        Expired tokens must raise AuthenticationException.

        This enforces token expiration in auth flows.
        """
        payload = {
            "sub": str(uuid4()),
            "supabase_id": str(uuid4()),
            "user_id": 1,
            "exp": int((datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp()),
            "iat": int((datetime.now(timezone.utc) - timedelta(minutes=10)).timestamp()),
            "token_type": "access",
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        with pytest.raises(AuthenticationException, match="Token has expired"):
            security.decode_token(token)

    def test_decode_token_invalid_raises(self):
        """
        Malformed tokens must raise AuthenticationException.

        This prevents bad tokens from passing validation.
        """
        with pytest.raises(AuthenticationException, match="Invalid authentication credentials"):
            security.decode_token("not-a-jwt")

    def test_decode_token_claims_error_raises(self, monkeypatch):
        """
        JWT claims errors must raise AuthenticationException.
        """
        def boom(*args, **kwargs):
            raise jwt.JWTClaimsError("bad claims")

        monkeypatch.setattr(security.jwt, "decode", boom)
        with pytest.raises(AuthenticationException, match="Invalid authentication credentials"):
            security.decode_token("token")

    def test_decode_token_generic_error_raises(self, monkeypatch):
        """
        Unexpected decode errors must raise AuthenticationException.
        """
        def boom(*args, **kwargs):
            raise Exception("boom")

        monkeypatch.setattr(security.jwt, "decode", boom)
        with pytest.raises(AuthenticationException, match="Invalid authentication credentials"):
            security.decode_token("token")


class TestValidateTokenRefresh:
    def test_refresh_token_type_mismatch_raises(self):
        """
        Access tokens must not be accepted for refresh.

        This enforces the refresh-token boundary.
        """
        supabase_id = uuid4()
        token = security.create_token(
            supabase_id=supabase_id,
            user_id=1,
            token_type="access",
            user_role="seeker"
        )
        with pytest.raises(AuthenticationException, match="Invalid token type"):
            security.validate_token_refresh(token, current_supabase_id=supabase_id)

    def test_refresh_token_supabase_mismatch_raises(self):
        """
        Refresh token must match the current user.

        This prevents token reuse across accounts.
        """
        supabase_id = uuid4()
        token = security.create_token(
            supabase_id=supabase_id,
            user_id=1,
            token_type="refresh",
            user_role="seeker"
        )
        with pytest.raises(AuthenticationException, match="Invalid refresh token"):
            security.validate_token_refresh(token, current_supabase_id=uuid4())

    def test_refresh_token_success_returns_access_token(self):
        """
        Valid refresh tokens should return a new access token.
        """
        supabase_id = uuid4()
        token = security.create_token(
            supabase_id=supabase_id,
            user_id=1,
            token_type="refresh",
            user_role="seeker"
        )
        new_access = security.validate_token_refresh(token, current_supabase_id=supabase_id)
        assert isinstance(new_access, str)
        assert new_access

    def test_refresh_token_unexpected_error_raises(self, monkeypatch):
        """
        Unexpected errors during refresh must raise AuthenticationException.
        """
        def boom(*args, **kwargs):
            raise Exception("boom")

        monkeypatch.setattr(security, "decode_token", boom)
        with pytest.raises(AuthenticationException, match="Token refresh failed"):
            security.validate_token_refresh("token", current_supabase_id=uuid4())
