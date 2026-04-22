# tests/core/test_dependencies.py
"""
Targeted tests for app/api/dependencies.py.
Focus: auth branches, role gates, and request size protection.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from starlette.requests import Request
from jose import jwt

from app.api import dependencies as deps
from app.core.config import settings
from app.core.security import create_token


class TestRequestSizeValidation:
    def test_validate_request_size_rejects_large_body(self):
        """
        Oversized request bodies must be rejected with 413.

        This enforces the DoS protection guardrail.
        """
        scope = {
            "type": "http",
            "headers": [(b"content-length", str(deps.MAX_REQUEST_BODY_SIZE + 1).encode())],
        }
        request = Request(scope)
        with pytest.raises(HTTPException) as exc:
            deps.validate_request_size(request)
        assert exc.value.status_code == 413

    def test_validate_request_size_allows_small_body(self):
        """
        Requests below limit should pass.

        This avoids false positives on valid payloads.
        """
        scope = {
            "type": "http",
            "headers": [(b"content-length", b"1024")],
        }
        request = Request(scope)
        deps.validate_request_size(request)


class TestCurrentUser:
    def test_get_current_user_rejects_missing_subject(self, db):
        """
        Tokens without supabase_id or sub must 401.

        This prevents ambiguous user resolution.
        """
        token = jwt.encode({}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        with pytest.raises(HTTPException) as exc:
            deps.get_current_user(db=db, token=token)
        assert exc.value.status_code == 401

    def test_get_current_user_user_id_mismatch_raises(self, db, normal_user):
        """
        Token user_id mismatch must 401.

        This prevents token replay with altered user_id claims.
        """
        token = create_token(
            supabase_id=normal_user.supabase_id,
            user_id=normal_user.user_id + 999,
            user_role=normal_user.user_role.value
        )
        with pytest.raises(HTTPException) as exc:
            deps.get_current_user(db=db, token=token)
        assert exc.value.status_code == 401

    def test_get_current_user_missing_user_raises(self, db):
        """
        Valid tokens for non-existent users must 401.

        This prevents orphaned tokens from authenticating.
        """
        token = create_token(
            supabase_id=uuid4(),
            user_id=999999,
            user_role="seeker"
        )
        with pytest.raises(HTTPException) as exc:
            deps.get_current_user(db=db, token=token)
        assert exc.value.status_code == 401

    def test_get_current_user_falls_back_to_signed_user_id_and_heals_supabase_id(self, db, normal_user):
        """
        First-party JWTs carry both supabase_id and user_id.

        If the UUID on the local row is stale but the signed user_id still
        matches, the dependency should recover that account and write the fresh
        Supabase UUID back to the row instead of breaking the session.
        """
        stale_uuid = normal_user.supabase_id
        repaired_uuid = uuid4()
        normal_user.supabase_id = stale_uuid
        db.add(normal_user)
        db.commit()

        token = create_token(
            supabase_id=repaired_uuid,
            user_id=normal_user.user_id,
            user_role=normal_user.user_role.value
        )

        resolved_user = deps.get_current_user(db=db, token=token)

        db.refresh(normal_user)
        assert resolved_user.user_id == normal_user.user_id
        assert normal_user.supabase_id == repaired_uuid

    def test_get_current_user_unexpected_exception_raises(self, db, monkeypatch):
        """
        Unexpected decode errors must surface as 401.

        This covers the generic exception branch.
        """
        def boom(*args, **kwargs):
            raise Exception("boom")

        monkeypatch.setattr(deps, "decode_token", boom)
        with pytest.raises(HTTPException) as exc:
            deps.get_current_user(db=db, token="token")
        assert exc.value.status_code == 401

    def test_get_current_user_optional_none_when_no_token(self, db):
        """
        Optional auth must return None when no token is provided.

        This supports endpoints that allow anonymous access.
        """
        result = deps.get_current_user_optional(db=db, token=None)
        assert result is None

    def test_get_current_user_optional_returns_none_on_http_exception(self, db):
        """
        Optional auth should swallow HTTPException and return None.
        """
        result = deps.get_current_user_optional(db=db, token="invalid")
        assert result is None


class TestActiveUserAndRoles:
    def test_get_current_active_user_inactive_raises(self, normal_user):
        """
        Soft-deleted users must be blocked.

        This enforces account inactivity checks.
        """
        normal_user.deleted_at = datetime.now(timezone.utc)
        with pytest.raises(HTTPException) as exc:
            deps.get_current_active_user(current_user=normal_user)
        assert exc.value.status_code == 403

    def test_get_current_admin_user_requires_admin(self, normal_user, admin_user):
        """
        Admin-only dependency must reject non-admins.

        This prevents privilege escalation.
        """
        with pytest.raises(HTTPException) as exc:
            deps.get_current_admin_user(current_user=normal_user)
        assert exc.value.status_code == 403
        assert deps.get_current_admin_user(current_user=admin_user) == admin_user

    def test_get_current_agent_user_requires_agent(self, normal_user, agent_user):
        """
        Agent-only dependency must reject non-agents.

        This ensures role-based access control.
        """
        with pytest.raises(HTTPException) as exc:
            deps.get_current_agent_user(current_user=normal_user)
        assert exc.value.status_code == 403
        assert deps.get_current_agent_user(current_user=agent_user) == agent_user

    def test_get_current_seeker_user_requires_seeker(self, agent_user, normal_user):
        """
        Seeker-only dependency must reject non-seekers.

        This keeps seeker-only flows protected.
        """
        with pytest.raises(HTTPException) as exc:
            deps.get_current_seeker_user(current_user=agent_user)
        assert exc.value.status_code == 403
        assert deps.get_current_seeker_user(current_user=normal_user) == normal_user


class TestAgencyDependencies:
    def test_get_current_agency_returns_none_for_no_agency(self, db, normal_user):
        """
        Users without agency_id should return None.

        This avoids false positives in multi-tenant checks.
        """
        result = deps.get_current_agency(current_user=normal_user, db=db)
        assert result is None

    def test_get_current_agency_returns_agency(self, db, agent_user, agency):
        """
        Agency users should resolve their agency.

        This is required for tenant-scoped endpoints.
        """
        result = deps.get_current_agency(current_user=agent_user, db=db)
        assert result is not None
        assert result.agency_id == agency.agency_id

    def test_require_agency_raises_when_missing(self):
        """
        Missing agency context must 403.

        This blocks agency-scoped operations without membership.
        """
        with pytest.raises(HTTPException) as exc:
            deps.require_agency(agency=None)
        assert exc.value.status_code == 403

    def test_require_agency_returns_agency(self, agency):
        """
        Valid agency should pass through require_agency.
        """
        assert deps.require_agency(agency=agency) == agency


class TestProtectedRoute:
    def test_protected_route_returns_current_user(self, normal_user):
        """
        Protected routes should return the authenticated user.

        This enables downstream use of the principal.
        """
        assert deps.protected_route(current_user=normal_user) == normal_user
