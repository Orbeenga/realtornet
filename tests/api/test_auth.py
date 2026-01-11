# tests/api/test_auth.py
"""
Authentication endpoint tests.
Tests login, registration, token refresh, and current user endpoints.
"""

import pytest
from fastapi import status

from app.core.config import settings
from tests.utils import get_auth_headers


class TestAuth:
    """Test suite for authentication endpoints."""
    
    def test_login_success(self, client, normal_user):
        """Test successful login returns valid tokens."""
        data = {"username": "user@example.com", "password": "password"}
        response = client.post(f"{settings.API_V1_STR}/auth/login", data=data)
        
        assert response.status_code == status.HTTP_200_OK
        tokens = response.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"
        assert "expires_in" in tokens
    
    def test_login_wrong_password(self, client, normal_user):
        """Test login with incorrect password fails."""
        data = {"username": "user@example.com", "password": "wrong_password"}
        response = client.post(f"{settings.API_V1_STR}/auth/login", data=data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_login_nonexistent_user(self, client):
        """Test login with non-existent email fails."""
        data = {"username": "nonexistent@example.com", "password": "password"}
        response = client.post(f"{settings.API_V1_STR}/auth/login", data=data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_login_inactive_user(self, client, db, normal_user):
        """Test login with soft-deleted user fails."""
        # Soft delete the user
        from datetime import datetime, timezone
        normal_user.deleted_at = datetime.now(timezone.utc)
        db.commit()
        
        data = {"username": "user@example.com", "password": "password"}
        response = client.post(f"{settings.API_V1_STR}/auth/login", data=data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_token_refresh(self, client, normal_user):
        """Test refresh token endpoint returns new access token."""
        # First login to get refresh token
        data = {"username": "user@example.com", "password": "password"}
        login_response = client.post(f"{settings.API_V1_STR}/auth/login", data=data)
        tokens = login_response.json()
        
        # Use refresh token to get new access token
        refresh_data = {"refresh_token": tokens["refresh_token"]}
        response = client.post(
            f"{settings.API_V1_STR}/auth/refresh", 
            json=refresh_data
        )
        
        assert response.status_code == status.HTTP_200_OK
        new_tokens = response.json()
        assert "access_token" in new_tokens
        # New access token should be different
        assert new_tokens["access_token"] != tokens["access_token"]
        # Refresh token stays the same
        assert new_tokens["refresh_token"] == tokens["refresh_token"]
    
    def test_token_refresh_invalid_token(self, client):
        """Test refresh with invalid token fails."""
        refresh_data = {"refresh_token": "invalid_token"}
        response = client.post(
            f"{settings.API_V1_STR}/auth/refresh", 
            json=refresh_data
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_register_success(self, client):
        """Test new user registration."""
        user_data = {
            "email": "newuser@example.com",
            "password": "strongpassword123",  # Meet password requirements
            "first_name": "New",
            "last_name": "User",
            "phone_number": "+1234567899"
        }
        response = client.post(
            f"{settings.API_V1_STR}/auth/register", 
            json=user_data
        )
        
        assert response.status_code == status.HTTP_200_OK
        new_user = response.json()
        assert new_user["email"] == user_data["email"]
        assert "user_id" in new_user or "id" in new_user
        # Password should never be in response
        assert "password" not in new_user
        assert "password_hash" not in new_user
    
    def test_register_existing_email(self, client, normal_user):
        """Test registration with existing email fails."""
        user_data = {
            "email": "user@example.com",  # Same as normal_user
            "password": "strongpassword123",
            "first_name": "Another",
            "last_name": "User",
            "phone_number": "+1234567898"
        }
        response = client.post(
            f"{settings.API_V1_STR}/auth/register", 
            json=user_data
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_register_invalid_email(self, client):
        """Test registration with invalid email format fails."""
        user_data = {
            "email": "not-an-email",
            "password": "strongpassword123",
            "first_name": "Test",
            "last_name": "User"
        }
        response = client.post(
            f"{settings.API_V1_STR}/auth/register", 
            json=user_data
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_me_endpoint(self, client, normal_user):
        """Test get current user endpoint with valid token."""
        # Fixed: Pass both supabase_id and user_id
        headers = get_auth_headers(
            supabase_id=normal_user.supabase_id,
            user_id=normal_user.user_id,
            user_role=normal_user.user_role.value if hasattr(normal_user.user_role, 'value') else str(normal_user.user_role)
        )
        response = client.get(
            f"{settings.API_V1_STR}/auth/me", 
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        user_data = response.json()
        assert user_data["email"] == normal_user.email
        assert user_data["user_id"] == normal_user.user_id or user_data["id"] == normal_user.user_id
    
    def test_me_invalid_token(self, client):
        """Test me endpoint with invalid token fails."""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get(
            f"{settings.API_V1_STR}/auth/me", 
            headers=headers
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_me_no_token(self, client):
        """Test me endpoint without token fails."""
        response = client.get(f"{settings.API_V1_STR}/auth/me")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_token_expiration(self, client, normal_user):
        """Test that expired tokens are rejected."""
        # This test would require mocking time or using very short expiration
        # Skipping implementation as it requires time manipulation
        pytest.skip("Requires time mocking - implement with freezegun if needed")