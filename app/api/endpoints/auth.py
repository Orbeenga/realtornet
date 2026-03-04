# app/api/endpoints/auth.py
"""
Authentication endpoints - Canonical compliant
Handles login, registration, token refresh with proper soft delete and audit tracking
"""
from uuid import UUID
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

# --- DIRECT CRUD IMPORTS ---
from app.crud.users import user as user_crud

# --- DIRECT DEPENDENCY IMPORTS ---
from app.api.dependencies import get_db, get_current_active_user, validate_request_size

# --- DIRECT CORE IMPORTS ---
from app.core.security import generate_access_token, generate_refresh_token, decode_token
from app.core.config import settings

# --- DIRECT SCHEMA IMPORTS ---
from app.schemas.token import Token, TokenRefresh
from app.schemas.users import UserCreate, UserResponse

# --- TASK IMPORTS ---
from app.tasks.email_tasks import send_welcome_email

router = APIRouter()


@router.post("/login", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    
    Validates:
    - User exists and not soft-deleted
    - Password correct
    - User is active
    """
    # Authenticate user with email and password
    # CRUD layer filters deleted_at IS NULL automatically
    user = user_crud.authenticate(
        db, 
        email=form_data.username, 
        password=form_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active (not deactivated)
    if not user_crud.is_active(user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Generate access token with user's role
    # Uses both supabase_id (UUID) and user_id (BIGINT)
    access_token = generate_access_token(
        supabase_id=user.supabase_id,
        user_id=user.user_id,
        user_role=user.user_role.value if user.user_role else None,
        agency_id=user.agency_id
    )
    
    # Generate refresh token
    refresh_token = generate_refresh_token(
        supabase_id=user.supabase_id,
        user_id=user.user_id,
        user_role=user.user_role.value if user.user_role else None,
        agency_id=user.agency_id
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.post("/refresh", response_model=Token)
def refresh_access_token(
    db: Session = Depends(get_db),
    refresh_token_data: TokenRefresh = Body(...),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Refresh access token using a valid refresh token.
    
    Validates:
    - Token is valid and type is 'refresh'
    - User still exists and not soft-deleted
    - User is still active
    """
    try:
        # Decode the refresh token
        refresh_payload = decode_token(refresh_token_data.refresh_token)
        
        # Ensure it's a refresh token
        if refresh_payload.token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user from database to verify they still exist and are active
        # Use user_id from token payload (BIGINT)
        user_id = refresh_payload.user_id
        
        # CRUD filters deleted_at IS NULL automatically
        user = user_crud.get(db, user_id=user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user_crud.is_active(user):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User inactive or deleted",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Generate new access token with full user data
        new_access_token = generate_access_token(
            supabase_id=UUID(refresh_payload.supabase_id),
            user_id=refresh_payload.user_id,
            user_role=refresh_payload.role,
            agency_id=refresh_payload.agency_id
        )
        
        return {
            "access_token": new_access_token,
            "refresh_token": refresh_token_data.refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
        
    except ValueError:
        # Handle validation errors
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/register", response_model=UserResponse)
def register_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Create new user.
    
    Validates:
    - Email not already registered (including soft-deleted users)
    - User data meets schema requirements
    """
    # Check if user with email already exists
    # CRUD checks both active and soft-deleted users
    user = user_crud.get_by_email(db, email=user_in.email)
    
    if user:
        # Check if user is soft-deleted
        if user.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email was previously deleted. Please contact support.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )
    
    # Create new user
    # Generate supabase_id for registration (in real app, this comes from Supabase Auth)
    import uuid
    supabase_id = str(uuid.uuid4())  # In production, this would come from Supabase Auth callback
    
    # Pass supabase_id to create
    user = user_crud.create(db, obj_in=user_in, supabase_id=supabase_id)
    
    # Send welcome email as a background task
    send_welcome_email.delay(
        user.email,
        user.first_name
    )
    
    return user


@router.get("/me", response_model=UserResponse)
def read_users_me(
    current_user: Any = Depends(get_current_active_user),
) -> Any:
    """
    Get current authenticated user.
    
    Dependency ensures:
    - User is authenticated
    - User is active
    - User is not soft-deleted
    """
    return current_user
