# app/api/endpoints/agencies.py
"""
Agencies management endpoints - Canonical compliant
Handles real estate agencies (multi-tenant hub) with full audit trail and soft delete
"""
from datetime import datetime, timedelta, timezone
from typing import Any, List, cast  # Narrow dependency-backed values locally without changing the frozen endpoint contract.
import hashlib
from fastapi import APIRouter, Depends, HTTPException, Query, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
import logging

# --- DIRECT CRUD IMPORTS ---
from app.crud.agencies import agency as agency_crud
from app.crud.agent_profiles import agent_profile as agent_profile_crud
from app.crud.properties import property as property_crud
from app.crud.users import user as user_crud

# --- DIRECT DEPENDENCY IMPORTS ---
from app.api.dependencies import (
    get_db,
    get_current_user,
    get_current_user_optional,
    get_current_active_user,
    get_current_agency_owner_user,
    get_current_admin_user,
    validate_request_size,
    pagination_params,
)

# --- DIRECT SCHEMA IMPORTS ---
from app.schemas.users import UserResponse
from app.models.users import User  # Narrow endpoint-local user values back to the ORM shape expected by CRUD permission helpers.
from app.schemas.agencies import (
    AgencyResponse,
    AgencyAgentRosterResponse,
    AgencyApplicationCreate,
    AgencyApplicationResponse,
    AgencyCreate,
    AgencyInviteAcceptRequest,
    AgencyInviteAcceptResponse,
    AgencyInviteCreate,
    AgencyInviteResponse,
    AgencyInvitationResponse,
    AgencyAgentMembershipActionRequest,
    AgencyAgentMembershipResponse,
    AgencyJoinRequestCreate,
    AgencyJoinRequestRejectRequest,
    AgencyJoinRequestResponse,
    AgencyMembershipReviewRequestCreate,
    AgencyMembershipReviewDecisionRequest,
    AgencyMembershipReviewRequestResponse,
    AgencyUpdate
)
from app.schemas.properties import PropertyResponse
from app.core.config import settings
from app.models.agency_join_requests import AgencyAgentMembership, AgencyInvitation, AgencyJoinRequest, AgencyMembershipReviewRequest
from app.models.users import UserRole
from app.services.auth_user_sync_service import SupabaseUserSyncError, sync_supabase_auth_user_metadata

router = APIRouter()

# Set up logging
logger = logging.getLogger(__name__)

AGENCY_INVITE_TOKEN_TYPE = "agency_invite"


def _hash_agency_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _create_agency_invite_token(*, agency_id: int, email: str, invitation_id: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    payload: dict[str, Any] = {
        "token_type": AGENCY_INVITE_TOKEN_TYPE,
        "agency_id": agency_id,
        "email": email.lower(),
        "exp": int(expire.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    if invitation_id is not None:
        payload["invitation_id"] = invitation_id
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _decode_agency_invite_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invite token",
        ) from exc

    if payload.get("token_type") != AGENCY_INVITE_TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invite token",
        )
    return payload


def _agency_invitation_payload(invitation: AgencyInvitation) -> dict[str, Any]:
    agency = invitation.__dict__.get("agency")
    return {
        "invitation_id": invitation.invitation_id,
        "agency_id": invitation.agency_id,
        "agency_name": getattr(agency, "name", None) or "",
        "email": invitation.email,
        "invited_user_id": invitation.invited_user_id,
        "status": invitation.status,
        "created_at": invitation.created_at,
        "updated_at": invitation.updated_at,
        "expires_at": invitation.expires_at,
        "accepted_at": invitation.accepted_at,
        "rejected_at": invitation.rejected_at,
        "revoked_at": invitation.revoked_at,
    }


def _membership_payload(*, membership: AgencyAgentMembership, user: User) -> dict[str, Any]:
    profile = getattr(membership, "agent_profile", None) or getattr(user, "agent_profile", None)
    return {
        "user_id": user.user_id,
        "agency_id": membership.agency_id,
        "membership_id": membership.membership_id,
        "membership_status": membership.status,
        "status_reason": membership.status_reason,
        "status_decided_at": membership.status_decided_at,
        "status_decided_by": membership.status_decided_by,
        "display_name": getattr(user, "full_name", None) or user.email,
        "email": user.email,
        "phone_number": user.phone_number,
        "profile_image_url": user.profile_image_url,
        "profile_id": getattr(profile, "profile_id", None),
        "specialization": getattr(profile, "specialization", None),
        "years_experience": getattr(profile, "years_experience", None),
        "license_number": getattr(profile, "license_number", None),
        "bio": getattr(profile, "bio", None),
        "company_name": getattr(profile, "company_name", None),
        "pending_review_request_id": None,
        "pending_review_reason": None,
        "pending_review_submitted_at": None,
        "created_at": membership.created_at,
        "updated_at": membership.updated_at,
    }


def _attach_pending_review_payload(
    payload: dict[str, Any],
    review_request: AgencyMembershipReviewRequest | None,
) -> dict[str, Any]:
    if review_request is None:
        return payload
    payload["pending_review_request_id"] = review_request.review_request_id
    payload["pending_review_reason"] = review_request.reason
    payload["pending_review_submitted_at"] = review_request.created_at
    return payload


def _ensure_active_agency_membership(
    *,
    db: Session,
    agency_id: int,
    user: User,
    actor: User,
    source_join_request_id: int | None = None,
) -> AgencyAgentMembership:
    profile = agent_profile_crud.get_by_user_id(db, user_id=cast(int, user.user_id))
    existing_membership = db.execute(
        select(AgencyAgentMembership).where(
            AgencyAgentMembership.agency_id == agency_id,
            AgencyAgentMembership.user_id == user.user_id,
        )
    ).scalar_one_or_none()
    if existing_membership is None:
        existing_membership = AgencyAgentMembership(
            agency_id=agency_id,
            user_id=user.user_id,
            agent_profile_id=getattr(profile, "profile_id", None),
            status="active",
            source_join_request_id=source_join_request_id,
            created_by=actor.supabase_id,
        )
        db.add(existing_membership)
    else:
        cast(Any, existing_membership).deleted_at = None
        cast(Any, existing_membership).deleted_by = None
        cast(Any, existing_membership).status = "active"
        cast(Any, existing_membership).agent_profile_id = getattr(profile, "profile_id", None)
        if source_join_request_id is not None:
            cast(Any, existing_membership).source_join_request_id = source_join_request_id
        existing_membership.updated_by = actor.supabase_id
        db.add(existing_membership)

    db.flush()
    db.refresh(existing_membership)
    return existing_membership


def _is_agency_owner_for(*, user: User | None, agency_id: int) -> bool:
    return (
        user is not None
        and cast(UserRole, user.user_role) in {UserRole.AGENCY_OWNER, UserRole.ADMIN}
        and (cast(UserRole, user.user_role) == UserRole.ADMIN or cast(int | None, user.agency_id) == agency_id)
    )


def _get_owned_agency_membership(
    *,
    db: Session,
    agency_id: int,
    membership_id: int,
    current_user: User,
) -> AgencyAgentMembership:
    if cast(int | None, current_user.agency_id) != agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agency owners can only manage their own agency",
        )

    agency = agency_crud.get(db, agency_id=agency_id)
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found",
        )

    membership = db.execute(
        select(AgencyAgentMembership).where(
            AgencyAgentMembership.membership_id == membership_id,
            AgencyAgentMembership.agency_id == agency_id,
            AgencyAgentMembership.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency membership not found",
        )
    return membership


def _set_membership_status(
    *,
    db: Session,
    membership: AgencyAgentMembership,
    current_user: User,
    status_value: str,
    reason: str | None,
) -> AgencyAgentMembership:
    cast(Any, membership).status = status_value
    cast(Any, membership).status_reason = reason
    cast(Any, membership).status_decided_at = datetime.now(timezone.utc)
    membership.status_decided_by = current_user.user_id
    membership.updated_by = current_user.supabase_id
    db.add(membership)
    db.flush()
    db.refresh(membership)
    return membership


def _first_active_membership_agency_for_user(*, db: Session, user_id: int) -> int | None:
    return db.execute(
        select(AgencyAgentMembership.agency_id)
        .where(
            AgencyAgentMembership.user_id == user_id,
            AgencyAgentMembership.status == "active",
            AgencyAgentMembership.deleted_at.is_(None),
        )
        .order_by(AgencyAgentMembership.created_at.asc())
    ).scalar_one_or_none()


def _apply_membership_role_after_status_change(
    *,
    db: Session,
    membership: AgencyAgentMembership,
    actor: User,
    new_status: str,
) -> tuple[User, bool]:
    member = user_crud.get(db, user_id=cast(int, membership.user_id))
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency member user not found",
        )

    member_role = cast(UserRole, member.user_role)
    if member_role in {UserRole.ADMIN, UserRole.AGENCY_OWNER}:
        return member, False

    update_payload: dict[str, Any] = {}
    if new_status == "active":
        if member_role == UserRole.SEEKER:
            update_payload["user_role"] = UserRole.AGENT
        if cast(int | None, member.agency_id) is None:
            update_payload["agency_id"] = membership.agency_id
    elif new_status == "inactive":
        remaining_active_agency_id = _first_active_membership_agency_for_user(
            db=db,
            user_id=cast(int, member.user_id),
        )
        if remaining_active_agency_id is None:
            if member_role == UserRole.AGENT:
                update_payload["user_role"] = UserRole.SEEKER
            if cast(int | None, member.agency_id) is not None:
                update_payload["agency_id"] = None
        elif cast(int | None, member.agency_id) != remaining_active_agency_id:
            update_payload["agency_id"] = remaining_active_agency_id

    if update_payload:
        member = user_crud.update(
            db,
            db_obj=member,
            obj_in=update_payload,
            updated_by=str(actor.supabase_id),
        )
        return member, True
    return member, False


def _set_membership_status_and_sync_user(
    *,
    db: Session,
    membership: AgencyAgentMembership,
    current_user: User,
    status_value: str,
    reason: str | None,
) -> AgencyAgentMembership:
    try:
        membership = _set_membership_status(
            db=db,
            membership=membership,
            current_user=current_user,
            status_value=status_value,
            reason=reason,
        )
        member, user_changed = _apply_membership_role_after_status_change(
            db=db,
            membership=membership,
            actor=current_user,
            new_status=status_value,
        )
        if user_changed:
            sync_supabase_auth_user_metadata(member)
        db.flush()
        db.refresh(membership)
        return membership
    except SupabaseUserSyncError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


def _expire_invitation_if_needed(*, db: Session, invitation: AgencyInvitation) -> AgencyInvitation:
    if str(invitation.status) == "pending" and cast(datetime, invitation.expires_at) <= datetime.now(timezone.utc):
        cast(Any, invitation).status = "expired"
        db.add(invitation)
        db.flush()
        db.refresh(invitation)
    return invitation


def _get_pending_invitation_or_raise(*, db: Session, invitation_id: int, current_user: User) -> AgencyInvitation:
    invitation = db.execute(
        select(AgencyInvitation)
        .options(joinedload(AgencyInvitation.agency))
        .where(
            AgencyInvitation.invitation_id == invitation_id,
            AgencyInvitation.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency invitation not found",
        )

    current_email = str(current_user.email).lower()
    if str(invitation.email).lower() != current_email and cast(int | None, invitation.invited_user_id) != cast(int, current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agency invitation does not belong to the current user",
        )

    invitation = _expire_invitation_if_needed(db=db, invitation=invitation)
    if str(invitation.status) != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agency invitation is {invitation.status}",
        )
    return invitation


def _accept_agency_invitation_for_user(
    *,
    db: Session,
    invitation: AgencyInvitation,
    invited_user: User,
    actor: User,
) -> AgencyInviteAcceptResponse:
    agency_id = cast(int, invitation.agency_id)
    update_payload: dict[str, Any] = {}
    if cast(UserRole, invited_user.user_role) == UserRole.SEEKER:
        update_payload["user_role"] = UserRole.AGENT
    if cast(int | None, invited_user.agency_id) is None:
        update_payload["agency_id"] = agency_id
    try:
        if update_payload:
            invited_user = user_crud.update(
                db,
                db_obj=invited_user,
                obj_in=update_payload,
                updated_by=str(actor.supabase_id),
            )
            sync_supabase_auth_user_metadata(invited_user)
        _ensure_active_agency_membership(
            db=db,
            agency_id=agency_id,
            user=invited_user,
            actor=actor,
        )
        cast(Any, invitation).status = "accepted"
        cast(Any, invitation).accepted_at = datetime.now(timezone.utc)
        cast(Any, invitation).invited_user_id = invited_user.user_id
        invitation.updated_by = actor.supabase_id
        db.add(invitation)
        db.flush()
        db.refresh(invitation)
    except SupabaseUserSyncError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return AgencyInviteAcceptResponse(
        status="accepted",
        agency_id=agency_id,
        user_id=cast(int, invited_user.user_id),
        invitation_id=cast(int, invitation.invitation_id),
        email=cast(str, invitation.email),
    )


@router.get("/", response_model=List[AgencyResponse])
def read_agencies(
    db: Session = Depends(get_db),
    pagination: dict = Depends(pagination_params),
) -> Any:
    """
    Retrieve agencies.
    
    Public endpoint - returns only non-deleted agencies.
    Used for browsing agencies or populating agency selection.
    CRUD layer enforces deleted_at IS NULL filtering.
    """
    agencies = agency_crud.get_multi(db, **pagination,)
    return agencies


@router.post("/apply/", response_model=AgencyApplicationResponse, status_code=status.HTTP_201_CREATED)
def apply_for_agency(
    *,
    db: Session = Depends(get_db),
    agency_in: AgencyApplicationCreate,
    _: None = Depends(validate_request_size),
) -> Any:
    """
    Public agency application.

    Applications start pending. Admin approval later promotes the owner account
    attached to owner_email.
    """
    if agency_crud.get_by_name(db, name=agency_in.name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agency with this name already exists",
        )

    agency_email = agency_in.email or agency_in.owner_email
    if agency_email and agency_crud.get_by_email(db, email=str(agency_email)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agency with this email already exists",
        )

    agency = agency_crud.create_application(db, obj_in=agency_in)
    return {"agency_id": agency.agency_id, "status": agency.status}


@router.post("/accept-invite/", response_model=AgencyInviteAcceptResponse)
def accept_agency_invite(
    *,
    db: Session = Depends(get_db),
    invite_in: AgencyInviteAcceptRequest,
    _: None = Depends(validate_request_size),
) -> Any:
    payload = _decode_agency_invite_token(invite_in.invite_token)
    email = str(payload.get("email", "")).lower()
    raw_agency_id = payload.get("agency_id")
    if raw_agency_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invite token",
        )
    agency_id = int(raw_agency_id)
    invitation_id = payload.get("invitation_id")

    agency = agency_crud.get(db, agency_id=agency_id)
    if agency is None or str(agency.status) != "approved":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found",
        )

    invitation: AgencyInvitation | None = None
    if invitation_id is not None:
        invitation = db.execute(
            select(AgencyInvitation).where(
                AgencyInvitation.invitation_id == int(invitation_id),
                AgencyInvitation.agency_id == agency_id,
                AgencyInvitation.email == email,
                AgencyInvitation.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
    if invitation is None:
        invitation = db.execute(
            select(AgencyInvitation).where(
                AgencyInvitation.agency_id == agency_id,
                AgencyInvitation.email == email,
                AgencyInvitation.token_hash == _hash_agency_invite_token(invite_in.invite_token),
                AgencyInvitation.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
    if invitation is not None:
        invitation = _expire_invitation_if_needed(db=db, invitation=invitation)
        if str(invitation.status) != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Agency invitation is {invitation.status}",
            )

    invited_user = user_crud.get_by_email(db, email=email)
    if invited_user is None:
        return {
            "status": "registration_required",
            "agency_id": agency_id,
            "invitation_id": invitation.invitation_id if invitation is not None else None,
            "redirect_url": f"/register?invite_token={invite_in.invite_token}",
            "email": email,
        }

    if invitation is None:
        invitation = AgencyInvitation(
            agency_id=agency_id,
            email=email,
            invited_user_id=invited_user.user_id,
            status="pending",
            token_hash=_hash_agency_invite_token(invite_in.invite_token),
            expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc),
            created_by=invited_user.supabase_id,
        )
        db.add(invitation)
        db.flush()
        db.refresh(invitation)

    return _accept_agency_invitation_for_user(
        db=db,
        invitation=invitation,
        invited_user=invited_user,
        actor=invited_user,
    )


@router.get("/{agency_id}", response_model=AgencyResponse)
def read_agency(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
) -> Any:
    """
    Get agency by ID.
    
    Public endpoint - anyone can view agency details.
    Returns 404 if agency not found or soft-deleted.
    """
    agency = agency_crud.get(db, agency_id=agency_id)
    
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )
    
    return agency


@router.post("/", response_model=AgencyResponse, status_code=status.HTTP_201_CREATED)
def create_agency(
    *,
    db: Session = Depends(get_db),
    agency_in: AgencyCreate,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Create new agency. Admin only.
    
    Creates the multi-tenant container for agents and properties.
    Validates name and email uniqueness.
    
    Audit: Tracks creator via created_by (Supabase UUID).
    """
    # Check if agency with same name already exists
    existing_agency = agency_crud.get_by_name(db, name=agency_in.name)
    if existing_agency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agency with this name already exists"
        )
    
    # Check if agency with same email exists (if provided)
    if agency_in.email:
        existing_agency_email = agency_crud.get_by_email(db, email=agency_in.email)
        if existing_agency_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agency with this email already exists"
            )
    
    # Create with audit tracking
    agency = agency_crud.create(
        db, 
        obj_in=agency_in,
        created_by=str(current_user.supabase_id)  # Normalize the dependency UUID to the CRUD audit field's string type.
    )

    logger.info("Agency created", extra={
        "agency_id": agency.agency_id,
        "agency_name": agency.name,
        "created_by": str(current_user.supabase_id)
    })

    return agency


@router.put("/{agency_id}", response_model=AgencyResponse)
def update_agency(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    agency_in: AgencyUpdate,
    current_user: UserResponse = Depends(get_current_admin_user),
    _: None = Depends(validate_request_size)
) -> Any:
    """
    Update an agency. Admin only.
    
    Validates name and email uniqueness if being changed.
    
    Audit: Tracks updater via updated_by (Supabase UUID).
    """
    agency = agency_crud.get(db, agency_id=agency_id)
    
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )
    
    # If name is being changed, check uniqueness
    if agency_in.name and agency_in.name != agency.name:
        existing_agency = agency_crud.get_by_name(db, name=agency_in.name)
        if existing_agency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agency with this name already exists"
            )
    
    # If email is being changed, check uniqueness
    if agency_in.email and agency_in.email != agency.email:
        existing_agency_email = agency_crud.get_by_email(db, email=agency_in.email)
        if existing_agency_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agency with this email already exists"
            )
    
    # Update with audit tracking
    agency = agency_crud.update(
        db, 
        db_obj=agency, 
        obj_in=agency_in,
        updated_by=str(current_user.supabase_id)  # Normalize the dependency UUID to the CRUD audit field's string type.
    )

    logger.info("Agency updated", extra={
        "agency_id": agency.agency_id,
        "updated_by": str(current_user.supabase_id)
    })

    return agency


@router.delete("/{agency_id}", response_model=AgencyResponse)
def delete_agency(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    current_user: UserResponse = Depends(get_current_admin_user)
) -> Any:
    """
    Soft delete an agency. Admin only.
    
    CRITICAL: This is a multi-tenant hub operation.
    Sets deleted_at timestamp, preserves all data.
    
    Considerations:
    - Agents belonging to this agency remain (FK preserved)
    - Properties remain (FK preserved)
    - Consider business rules: prevent deletion if active agents/properties exist
    
    Audit: Tracks who deleted via deleted_by (Supabase UUID).
    """
    agency = agency_crud.get(db, agency_id=agency_id)
    
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )
    
    # Optional business rule: Prevent deletion if agency has active agents
    active_agents_count = user_crud.count_by_agency(db, agency_id=agency_id)
    if active_agents_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete agency with active agents. Reassign or remove agents first."
        )
    
    # Optional business rule: Prevent deletion if agency has active properties
    active_properties_count = property_crud.count_by_agency(db, agency_id=agency_id)
    if active_properties_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete agency with active properties. Remove properties first."
        )
    
    # Soft delete with audit trail
    agency = agency_crud.soft_delete(
        db, 
        agency_id=agency_id,
        deleted_by_supabase_id=str(current_user.supabase_id)  # Normalize the dependency UUID to the CRUD soft-delete audit field's string type.
    )

    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found during delete attempt"
        )

    logger.warning("Agency soft deleted", extra={
        "agency_id": agency_id,
        "agency_name": agency.name,
        "deleted_by": str(current_user.supabase_id)
    })

    return agency


@router.get("/{agency_id}/agents", response_model=List[AgencyAgentRosterResponse])
def read_agency_agents(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    current_user: User | None = Depends(get_current_user_optional),
    pagination: dict = Depends(pagination_params),
    membership_status: str = Query(default="active", alias="status"),
) -> Any:
    """
    Retrieve all agents belonging to an agency.
    
    Public endpoint - useful for "Meet Our Team" pages.
    Returns active agents by default. Agency owners can request all membership states.
    """
    # Verify agency exists
    agency = agency_crud.get(db, agency_id=agency_id)
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )
    
    allowed_statuses = {"active", "inactive", "suspended", "blocked", "all"}
    if membership_status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid agency membership status filter",
        )
    if membership_status != "active" and not _is_agency_owner_for(user=current_user, agency_id=agency_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agency owners can only view non-active membership states for their own agency",
        )

    query = (
        select(AgencyAgentMembership, User)
        .join(User, User.user_id == AgencyAgentMembership.user_id)
        .options(
            joinedload(AgencyAgentMembership.agent_profile),
            joinedload(AgencyAgentMembership.user).joinedload(User.agent_profile),
        )
        .where(
            AgencyAgentMembership.agency_id == agency_id,
            AgencyAgentMembership.deleted_at.is_(None),
            User.deleted_at.is_(None),
        )
        .order_by(AgencyAgentMembership.created_at.desc())
        .offset(pagination["skip"])
        .limit(pagination["limit"])
    )
    if membership_status == "active":
        query = query.where(AgencyAgentMembership.status == "active")
    elif membership_status != "all":
        query = query.where(AgencyAgentMembership.status == membership_status)
    membership_rows = db.execute(query).all()
    membership_ids = [cast(int, membership.membership_id) for membership, _ in membership_rows]
    pending_reviews: dict[int, AgencyMembershipReviewRequest] = {}
    if membership_ids:
        review_rows = db.execute(
            select(AgencyMembershipReviewRequest)
            .where(
                AgencyMembershipReviewRequest.membership_id.in_(membership_ids),
                AgencyMembershipReviewRequest.status == "pending",
                AgencyMembershipReviewRequest.deleted_at.is_(None),
            )
            .order_by(AgencyMembershipReviewRequest.created_at.desc())
        ).scalars()
        for review_request in review_rows:
            membership_id = cast(int, review_request.membership_id)
            if membership_id not in pending_reviews:
                pending_reviews[membership_id] = review_request

    return [
        _attach_pending_review_payload(
            _membership_payload(membership=membership, user=user),
            pending_reviews.get(cast(int, membership.membership_id)),
        )
        for membership, user in membership_rows
    ]


@router.patch("/{agency_id}/agents/{membership_id}/suspend/", response_model=AgencyAgentMembershipResponse)
def suspend_agency_agent_membership(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    membership_id: int,
    action_in: AgencyAgentMembershipActionRequest | None = None,
    current_user: UserResponse = Depends(get_current_agency_owner_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Suspend an active agency membership with an audit reason."""
    membership = _get_owned_agency_membership(
        db=db,
        agency_id=agency_id,
        membership_id=membership_id,
        current_user=cast(User, current_user),
    )
    return _set_membership_status_and_sync_user(
        db=db,
        membership=membership,
        current_user=cast(User, current_user),
        status_value="suspended",
        reason=action_in.reason if action_in is not None else None,
    )


@router.patch("/{agency_id}/agents/{membership_id}/revoke/", response_model=AgencyAgentMembershipResponse)
def revoke_agency_agent_membership(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    membership_id: int,
    action_in: AgencyAgentMembershipActionRequest | None = None,
    current_user: UserResponse = Depends(get_current_agency_owner_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Revoke an agency membership while retaining the affiliation audit trail."""
    membership = _get_owned_agency_membership(
        db=db,
        agency_id=agency_id,
        membership_id=membership_id,
        current_user=cast(User, current_user),
    )
    return _set_membership_status_and_sync_user(
        db=db,
        membership=membership,
        current_user=cast(User, current_user),
        status_value="inactive",
        reason=action_in.reason if action_in is not None else None,
    )


@router.patch("/{agency_id}/agents/{membership_id}/block/", response_model=AgencyAgentMembershipResponse)
def block_agency_agent_membership(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    membership_id: int,
    action_in: AgencyAgentMembershipActionRequest | None = None,
    current_user: UserResponse = Depends(get_current_agency_owner_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Block an agency membership while retaining the affiliation audit trail."""
    membership = _get_owned_agency_membership(
        db=db,
        agency_id=agency_id,
        membership_id=membership_id,
        current_user=cast(User, current_user),
    )
    return _set_membership_status_and_sync_user(
        db=db,
        membership=membership,
        current_user=cast(User, current_user),
        status_value="blocked",
        reason=action_in.reason if action_in is not None else None,
    )


@router.patch("/{agency_id}/agents/{membership_id}/restore/", response_model=AgencyAgentMembershipResponse)
def restore_agency_agent_membership(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    membership_id: int,
    action_in: AgencyAgentMembershipActionRequest | None = None,
    current_user: UserResponse = Depends(get_current_agency_owner_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Reactivate a revoked, suspended, or blocked agency membership."""
    membership = _get_owned_agency_membership(
        db=db,
        agency_id=agency_id,
        membership_id=membership_id,
        current_user=cast(User, current_user),
    )
    return _set_membership_status_and_sync_user(
        db=db,
        membership=membership,
        current_user=cast(User, current_user),
        status_value="active",
        reason=action_in.reason if action_in is not None else None,
    )


@router.post(
    "/{agency_id}/agents/{membership_id}/review-request/",
    response_model=AgencyMembershipReviewRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_agency_membership_review_request(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    membership_id: int,
    review_in: AgencyMembershipReviewRequestCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Allow an agent to request review of a revoked, suspended, or blocked membership."""
    current_user_model = cast(User, current_user)
    membership = db.execute(
        select(AgencyAgentMembership).where(
            AgencyAgentMembership.membership_id == membership_id,
            AgencyAgentMembership.agency_id == agency_id,
            AgencyAgentMembership.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency membership not found",
        )
    if cast(int, membership.user_id) != cast(int, current_user_model.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Users can only request review for their own agency memberships",
        )
    if str(membership.status) == "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Active agency memberships do not require review",
        )

    existing_review = db.execute(
        select(AgencyMembershipReviewRequest).where(
            AgencyMembershipReviewRequest.membership_id == membership_id,
            AgencyMembershipReviewRequest.status == "pending",
            AgencyMembershipReviewRequest.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if existing_review is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pending membership review request already exists",
        )

    review_request = AgencyMembershipReviewRequest(
        membership_id=membership_id,
        agency_id=agency_id,
        user_id=current_user_model.user_id,
        status="pending",
        reason=review_in.reason,
        created_by=current_user_model.supabase_id,
    )
    db.add(review_request)
    db.flush()
    db.refresh(review_request)
    return review_request


def _get_owned_membership_review_request(
    *,
    db: Session,
    agency_id: int,
    membership_id: int,
    review_request_id: int,
    current_user: User,
) -> tuple[AgencyAgentMembership, AgencyMembershipReviewRequest]:
    membership = _get_owned_agency_membership(
        db=db,
        agency_id=agency_id,
        membership_id=membership_id,
        current_user=current_user,
    )
    review_request = db.execute(
        select(AgencyMembershipReviewRequest).where(
            AgencyMembershipReviewRequest.review_request_id == review_request_id,
            AgencyMembershipReviewRequest.membership_id == membership_id,
            AgencyMembershipReviewRequest.agency_id == agency_id,
            AgencyMembershipReviewRequest.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if review_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership review request not found",
        )
    if str(review_request.status) != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Membership review request has already been reviewed",
        )
    return membership, review_request


@router.patch(
    "/{agency_id}/agents/{membership_id}/review-requests/{review_request_id}/approve/",
    response_model=AgencyMembershipReviewRequestResponse,
)
def approve_agency_membership_review_request(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    membership_id: int,
    review_request_id: int,
    decision_in: AgencyMembershipReviewDecisionRequest | None = None,
    current_user: UserResponse = Depends(get_current_agency_owner_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Approve an agent review request and reactivate the membership."""
    current_user_model = cast(User, current_user)
    membership, review_request = _get_owned_membership_review_request(
        db=db,
        agency_id=agency_id,
        membership_id=membership_id,
        review_request_id=review_request_id,
        current_user=current_user_model,
    )
    _set_membership_status_and_sync_user(
        db=db,
        membership=membership,
        current_user=current_user_model,
        status_value="active",
        reason=decision_in.reason if decision_in is not None else None,
    )
    cast(Any, review_request).status = "approved"
    cast(Any, review_request).response_reason = decision_in.reason if decision_in is not None else None
    cast(Any, review_request).decided_at = datetime.now(timezone.utc)
    review_request.decided_by = current_user_model.user_id
    review_request.updated_by = current_user_model.supabase_id
    db.add(review_request)
    db.flush()
    db.refresh(review_request)
    return review_request


@router.patch(
    "/{agency_id}/agents/{membership_id}/review-requests/{review_request_id}/reject/",
    response_model=AgencyMembershipReviewRequestResponse,
)
def reject_agency_membership_review_request(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    membership_id: int,
    review_request_id: int,
    decision_in: AgencyMembershipReviewDecisionRequest | None = None,
    current_user: UserResponse = Depends(get_current_agency_owner_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Reject an agent review request while retaining the membership state."""
    current_user_model = cast(User, current_user)
    _membership, review_request = _get_owned_membership_review_request(
        db=db,
        agency_id=agency_id,
        membership_id=membership_id,
        review_request_id=review_request_id,
        current_user=current_user_model,
    )
    cast(Any, review_request).status = "rejected"
    cast(Any, review_request).response_reason = decision_in.reason if decision_in is not None else None
    cast(Any, review_request).decided_at = datetime.now(timezone.utc)
    review_request.decided_by = current_user_model.user_id
    review_request.updated_by = current_user_model.supabase_id
    db.add(review_request)
    db.flush()
    db.refresh(review_request)
    return review_request


@router.get("/{agency_id}/properties", response_model=List[PropertyResponse])
def read_agency_properties(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    pagination: dict = Depends(pagination_params),
) -> Any:
    """
    Retrieve all properties managed by an agency.
    
    Public endpoint - shows agency's property portfolio.
    Returns only approved, non-deleted properties.
    """
    # Verify agency exists
    agency = agency_crud.get(db, agency_id=agency_id)
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )
    
    properties = property_crud.get_by_agency_approved(
        db, 
        agency_id=agency_id, 
        **pagination,
    )
    return properties


@router.post(
    "/{agency_id}/join-request/",
    response_model=AgencyJoinRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_agency_join_request(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    request_in: AgencyJoinRequestCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Create a pending request to affiliate with an approved agency."""
    current_user_model = cast(User, current_user)
    if cast(UserRole, current_user_model.user_role) not in {
        UserRole.SEEKER,
        UserRole.AGENT,
        UserRole.AGENCY_OWNER,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Join requests are available to seekers and agents",
        )

    agency = agency_crud.get(db, agency_id=agency_id)
    if agency is None or str(agency.status) != "approved":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found",
        )

    existing_membership = db.execute(
        select(AgencyAgentMembership).where(
            AgencyAgentMembership.agency_id == agency_id,
            AgencyAgentMembership.user_id == current_user_model.user_id,
            AgencyAgentMembership.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if existing_membership is not None:
        existing_status = str(existing_membership.status)
        if existing_status == "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already affiliated with this agency",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agency membership is not active; submit a review request instead",
        )

    existing_request = db.execute(
        select(AgencyJoinRequest).where(
            AgencyJoinRequest.agency_id == agency_id,
            AgencyJoinRequest.user_id == current_user_model.user_id,
            AgencyJoinRequest.status == "pending",
            AgencyJoinRequest.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if existing_request is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pending join request already exists for this agency",
        )

    join_request = AgencyJoinRequest(
        agency_id=agency_id,
        user_id=current_user_model.user_id,
        cover_note=request_in.cover_note,
        portfolio_details=request_in.portfolio_details,
        status="pending",
        created_by=current_user_model.supabase_id,
    )
    db.add(join_request)
    db.flush()
    db.refresh(join_request)
    return join_request


@router.get("/{agency_id}/join-requests/", response_model=List[AgencyJoinRequestResponse])
def read_agency_join_requests(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    current_user: UserResponse = Depends(get_current_agency_owner_user),
    pagination: dict = Depends(pagination_params),
    request_status: str = Query(default="pending", alias="status"),
) -> Any:
    """Return join requests for the authenticated agency owner."""
    current_user_model = cast(User, current_user)
    if cast(int | None, current_user_model.agency_id) != agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agency owners can only manage their own agency",
        )

    agency = agency_crud.get(db, agency_id=agency_id)
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found",
        )

    allowed_statuses = {"pending", "approved", "rejected", "all"}
    if request_status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid join request status filter",
        )

    query = (
        select(AgencyJoinRequest)
        .options(joinedload(AgencyJoinRequest.user))
        .where(
            AgencyJoinRequest.agency_id == agency_id,
            AgencyJoinRequest.deleted_at.is_(None),
        )
        .order_by(AgencyJoinRequest.created_at.asc())
    )
    if request_status != "all":
        query = query.where(AgencyJoinRequest.status == request_status)

    query = query.offset(pagination["skip"]).limit(pagination["limit"])
    return list(db.execute(query).scalars().all())


@router.patch("/{agency_id}/join-requests/{request_id}/approve/", response_model=AgencyJoinRequestResponse)
def approve_agency_join_request(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    request_id: int,
    current_user: UserResponse = Depends(get_current_agency_owner_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Approve a seeker join request and promote the seeker to agent."""
    current_user_model = cast(User, current_user)
    if cast(int | None, current_user_model.agency_id) != agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agency owners can only manage their own agency",
        )

    join_request = db.execute(
        select(AgencyJoinRequest).where(
            AgencyJoinRequest.join_request_id == request_id,
            AgencyJoinRequest.agency_id == agency_id,
            AgencyJoinRequest.deleted_at.is_(None),
        ).options(joinedload(AgencyJoinRequest.user))
    ).scalar_one_or_none()
    if join_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Join request not found",
        )
    if str(join_request.status) != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Join request has already been reviewed",
        )

    seeker = user_crud.get(db, user_id=cast(int, join_request.user_id))
    if seeker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seeker user not found",
        )

    actor_supabase_id = str(current_user_model.supabase_id)
    try:
        update_payload: dict[str, Any] = {}
        if cast(UserRole, seeker.user_role) == UserRole.SEEKER:
            update_payload["user_role"] = UserRole.AGENT
        if cast(int | None, seeker.agency_id) is None:
            update_payload["agency_id"] = agency_id
        if update_payload:
            seeker = user_crud.update(
                db,
                db_obj=seeker,
                obj_in=update_payload,
                updated_by=actor_supabase_id,
            )
        _ensure_active_agency_membership(
            db=db,
            agency_id=agency_id,
            user=seeker,
            actor=current_user_model,
            source_join_request_id=cast(int, join_request.join_request_id),
        )

        cast(Any, join_request).status = "approved"
        cast(Any, join_request).rejection_reason = None
        cast(Any, join_request).decided_at = datetime.now(timezone.utc)
        join_request.decided_by = current_user_model.user_id
        join_request.updated_by = current_user_model.supabase_id
        db.add(join_request)
        db.flush()
        sync_supabase_auth_user_metadata(seeker)
        db.refresh(join_request)
    except SupabaseUserSyncError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return join_request


@router.patch("/{agency_id}/join-requests/{request_id}/reject/", response_model=AgencyJoinRequestResponse)
def reject_agency_join_request(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    request_id: int,
    reject_in: AgencyJoinRequestRejectRequest | None = None,
    current_user: UserResponse = Depends(get_current_agency_owner_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """Reject a pending agency join request."""
    current_user_model = cast(User, current_user)
    if cast(int | None, current_user_model.agency_id) != agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agency owners can only manage their own agency",
        )

    join_request = db.execute(
        select(AgencyJoinRequest).where(
            AgencyJoinRequest.join_request_id == request_id,
            AgencyJoinRequest.agency_id == agency_id,
            AgencyJoinRequest.deleted_at.is_(None),
        ).options(joinedload(AgencyJoinRequest.user))
    ).scalar_one_or_none()
    if join_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Join request not found",
        )
    if str(join_request.status) != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Join request has already been reviewed",
        )

    cast(Any, join_request).status = "rejected"
    cast(Any, join_request).rejection_reason = reject_in.reason if reject_in is not None else None
    cast(Any, join_request).decided_at = datetime.now(timezone.utc)
    join_request.decided_by = current_user_model.user_id
    join_request.updated_by = current_user_model.supabase_id
    db.add(join_request)
    db.flush()
    db.refresh(join_request)
    return join_request


@router.get("/{agency_id}/invitations/", response_model=List[AgencyInvitationResponse])
def read_agency_invitations(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    invitation_status: str = Query(default="all", alias="status"),
    pagination: dict = Depends(pagination_params),
    current_user: UserResponse = Depends(get_current_agency_owner_user),
) -> Any:
    """List invitations sent by the current agency owner."""
    current_user_model = cast(User, current_user)
    if cast(int | None, current_user_model.agency_id) != agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agency owners can only view their own agency invitations",
        )

    allowed_statuses = {"pending", "accepted", "rejected", "expired", "revoked", "all"}
    if invitation_status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invitation status filter",
        )

    query = (
        select(AgencyInvitation)
        .options(joinedload(AgencyInvitation.agency))
        .where(
            AgencyInvitation.agency_id == agency_id,
            AgencyInvitation.deleted_at.is_(None),
        )
        .order_by(AgencyInvitation.created_at.desc())
    )
    if invitation_status != "all":
        query = query.where(AgencyInvitation.status == invitation_status)
    query = query.offset(pagination["skip"]).limit(pagination["limit"])
    return [_agency_invitation_payload(invitation) for invitation in db.execute(query).scalars().all()]


@router.post("/{agency_id}/invite/", response_model=AgencyInviteResponse)
def invite_agency_agent(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    invite_in: AgencyInviteCreate,
    current_user: UserResponse = Depends(get_current_agency_owner_user),
    _: None = Depends(validate_request_size),
) -> Any:
    """
    Create or refresh a pending agency invitation.
    """
    current_user_model = cast(User, current_user)
    current_agency_id = cast(int | None, current_user_model.agency_id)
    if current_agency_id != agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agency owners can only invite agents to their own agency",
        )

    agency = agency_crud.get(db, agency_id=agency_id)
    if agency is None or str(agency.status) != "approved":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found",
        )

    invite_email = str(invite_in.email).lower()
    invited_user = user_crud.get_by_email(db, email=invite_email)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    invitation = db.execute(
        select(AgencyInvitation).where(
            AgencyInvitation.agency_id == agency_id,
            AgencyInvitation.email == invite_email,
            AgencyInvitation.status == "pending",
            AgencyInvitation.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if invitation is None:
        invitation = AgencyInvitation(
            agency_id=agency_id,
            email=invite_email,
            invited_user_id=getattr(invited_user, "user_id", None),
            status="pending",
            expires_at=expires_at,
            created_by=current_user_model.supabase_id,
        )
        db.add(invitation)
        db.flush()
        db.refresh(invitation)
    else:
        cast(Any, invitation).invited_user_id = getattr(invited_user, "user_id", None)
        cast(Any, invitation).expires_at = expires_at
        invitation.updated_by = current_user_model.supabase_id
        db.add(invitation)
        db.flush()
        db.refresh(invitation)

    invite_token = _create_agency_invite_token(
        agency_id=agency_id,
        email=invite_email,
        invitation_id=cast(int, invitation.invitation_id),
    )
    cast(Any, invitation).token_hash = _hash_agency_invite_token(invite_token)
    db.add(invitation)
    db.flush()
    db.refresh(invitation)
    return {
        "invite_token": invite_token,
        "agency_id": agency_id,
        "email": invitation.email,
        "invitation_id": invitation.invitation_id,
        "status": invitation.status,
        "expires_at": invitation.expires_at,
    }


@router.get("/{agency_id}/stats")
def read_agency_stats(
    *,
    db: Session = Depends(get_db),
    agency_id: int,
    current_user: UserResponse = Depends(get_current_user)
) -> Any:
    """
    Get agency statistics.
    
    Permissions:
    - Agency agents can view their own agency stats
    - Admins can view any agency stats
    
    Returns: agent count, property count, active listings, etc.
    """
    # Verify agency exists
    agency = agency_crud.get(db, agency_id=agency_id)
    if agency is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found"
        )
    
    # Check authorization: agent of this agency or admin
    current_user_model = cast(User, current_user)  # Narrow the dependency response object to the ORM user shape expected by the CRUD authorization helper.
    if not user_crud.is_admin(current_user_model):
        # Check if user is an agent of this agency
        current_agency_id = cast(int | None, current_user_model.agency_id)  # Narrow the optional ORM agency foreign key before comparing it to the route parameter.
        if current_agency_id is None or current_agency_id != agency_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to view this agency's statistics"
            )
    
    stats = agency_crud.get_stats(db, agency_id=agency_id)
    return stats
