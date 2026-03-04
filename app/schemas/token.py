#app/schemas/token.py
"""
Token schemas for authentication responses.
Phase 2 Aligned: Direct usage of TokenPayload, no duplication
"""

from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

# Import canonical TokenPayload from security module
from app.core.security import TokenPayload


class Token(BaseModel):
    """
    Schema for token response (login/refresh endpoints).
    
    Returns both access and refresh tokens with metadata.
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(
        default=900,
        description="Access token expiration in seconds (15 minutes)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 900
            }
        }


class TokenRefresh(BaseModel):
    """
    Schema for refresh token request.
    Used when client wants to refresh an expired access token.
    """
    refresh_token: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }


class TokenData(BaseModel):
    """
    Simplified token data for dependency injection.
    
    Used in dependencies.py for extracting essential user info from decoded token.
    Removed duplication - use TokenPayload.user_id (int) instead of string conversion.
    
    Note: This is a lightweight schema. For full token validation, use TokenPayload directly.
    """
    supabase_id: UUID  # Primary public identifier
    user_id: int  # Internal database ID (BigInteger)
    role: Optional[str] = None
    agency_id: Optional[int] = None  # Multi-tenant context
    
    @staticmethod
    def from_payload(payload: TokenPayload) -> "TokenData":
        """
        Convert TokenPayload to TokenData for dependency injection.
        
        Args:
            payload: Validated TokenPayload from decode_token()
        
        Returns:
            TokenData with essential fields for request context
        """
        return TokenData(
            supabase_id=payload.supabase_id,
            user_id=payload.user_id,
            role=payload.role,
            agency_id=payload.agency_id
        )
    
    class Config:
        json_schema_extra = {
            "example": {
                "supabase_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": 12345,
                "role": "agent",
                "agency_id": 789
            }
        }


# Export TokenPayload for use in other modules (avoid circular imports)
__all__ = ["Token", "TokenRefresh", "TokenData", "TokenPayload"]
