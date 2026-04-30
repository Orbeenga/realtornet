# app/api/endpoints/auth.py
"""
Authentication endpoints - Canonical compliant
Handles login, registration, token refresh with proper soft delete and audit tracking
"""
import logging
from uuid import UUID
from typing import Any, cast as typing_cast  # Alias typing.cast so endpoint-local narrowing stays explicit without affecting runtime token helpers.
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

# --- DIRECT CRUD IMPORTS ---
from app.crud.agent_profiles import agent_profile as agent_profile_crud
from app.crud.profiles import profile as profile_crud
from app.crud.users import user as user_crud

# --- DIRECT DEPENDENCY IMPORTS ---
from app.api.dependencies import get_db, get_current_active_user, validate_request_size

# --- DIRECT CORE IMPORTS ---
from app.core.security import generate_access_token, generate_refresh_token, decode_token
from app.core.config import settings

# --- DIRECT SCHEMA IMPORTS ---
from app.schemas.token import Token, TokenRefresh
from app.schemas.users import UserCreate, UserResponse, UserRole
from app.schemas.agent_profiles import AgentProfileCreate
from app.schemas.profiles import ProfileCreate

# --- TASK IMPORTS ---
from app.tasks.email_tasks import dispatch_email_task, send_welcome_email
from app.services.auth_registration_service import (
    SupabaseRegistrationError,
    create_supabase_auth_user_for_registration,
    delete_supabase_auth_user,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _serialize_user_role(user_role: Any) -> str | None:
    """Normalize ORM enum or raw-string roles for JWT payloads."""
    if user_role is None:
        return None
    role_value = getattr(user_role, "value", user_role)
    if isinstance(role_value, str):
        return role_value
    return str(role_value)


def _normalize_public_registration(user_in: UserCreate) -> UserCreate:
    """
    Force public self-registration into the lowest-privilege role.

    The role model in this codebase is backend-owned. Browsers can suggest many
    things in a request body, but they must never be able to mint `agent` or
    `admin` permissions during a public signup flow.
    """
    return user_in.model_copy(update={"user_role": UserRole.SEEKER})


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
    user_supabase_id: UUID = typing_cast(UUID, user.supabase_id)  # Narrow the ORM-backed Supabase UUID before passing it into the token helper.
    user_id_value: int = typing_cast(int, user.user_id)  # Narrow the ORM-backed user ID before passing it into the token helper.
    user_role_value = _serialize_user_role(user.user_role)
    user_agency_id: int | None = typing_cast(int | None, user.agency_id)  # Narrow the optional ORM-backed agency ID before passing it into the token helper.
    access_token = generate_access_token(
        supabase_id=user_supabase_id,
        user_id=user_id_value,
        user_role=user_role_value,
        agency_id=user_agency_id
    )
    
    # Generate refresh token
    refresh_token = generate_refresh_token(
        supabase_id=user_supabase_id,
        user_id=user_id_value,
        user_role=user_role_value,
        agency_id=user_agency_id
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

    # Get user from database to verify they still exist and are active
    # Use user_id from token payload (BIGINT)
    user_id = refresh_payload.user_id
    if user_id is None:  # Narrow the decoded payload before loading the user record from the database.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

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
        user_id=user_id,  # Reuse the narrowed payload user ID without changing refresh-token behavior.
        user_role=refresh_payload.role,
        agency_id=refresh_payload.agency_id
    )

    return {
        "access_token": new_access_token,
        "refresh_token": refresh_token_data.refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


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
    - Supabase Auth identity is created before local domain records
    """
    # Public registration always creates seekers. Higher-trust roles are granted
    # later through internal workflows, never directly from browser input.
    user_in = _normalize_public_registration(user_in)

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
    
    try:
        supabase_id = create_supabase_auth_user_for_registration(user_in)
    except SupabaseRegistrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to create Supabase auth user during registration",
        ) from exc
    except Exception as exc:
        error_text = str(exc).lower()
        if "already" in error_text and ("registered" in error_text or "exists" in error_text):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists in Supabase Auth",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supabase auth registration failed",
        ) from exc

    try:
        user = user_crud.create(
            db,
            obj_in=user_in,
            supabase_id=supabase_id,
            created_by=supabase_id
        )

        # The profile endpoints already assume each user has a baseline profile.
        # Creating it here keeps registration and later profile editing aligned.
        full_name = f"{user_in.first_name} {user_in.last_name}".strip()
        profile_crud.create(
            db,
            obj_in=ProfileCreate(
                full_name=full_name,
                phone_number=user_in.phone_number,
                profile_picture=user_in.profile_image_url,
            ),
            user_id=typing_cast(int, user.user_id),
            created_by=supabase_id
        )

        if user_in.user_role == UserRole.AGENT:
            agent_profile_crud.create(
                db,
                obj_in=AgentProfileCreate(
                    user_id=typing_cast(int, user.user_id),
                    agency_id=typing_cast(int | None, user.agency_id)
                ),
                created_by=supabase_id
            )
    except Exception as exc:
        db.rollback()
        try:
            delete_supabase_auth_user(supabase_id)
        except Exception:
            logger.warning(
                "Supabase auth rollback failed after local registration error",
                extra={"supabase_id": supabase_id, "email": user_in.email},
                exc_info=True,
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User registration failed",
        ) from exc
    
    # Send welcome email without making registration success depend on delivery.
    email_task = typing_cast(Any, send_welcome_email)
    welcome_subject = "Welcome to RealtorNet"
    welcome_text = (
        f"Hi {user.first_name},\n\n"
        "Welcome to RealtorNet. Your account has been created successfully.\n\n"
        "You can now sign in and start exploring listings."
    )
    welcome_html = f"""
    <html>
        <body>
            <h2>Welcome to RealtorNet, {user.first_name}!</h2>
            <p>Your account has been created successfully.</p>
            <p>You can now sign in and start exploring listings.</p>
        </body>
    </html>
    """
    dispatch_email_task(
        email_task,
        user.email,
        welcome_subject,
        welcome_text,
        welcome_html,
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
