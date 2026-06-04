"""Centralized moderation lifecycle transition guard for property listings.

This module defines the canonical Phase M moderation transition matrix and a
single helper that enforces both legal from→to pairs and authority rules
(agent vs agency owner vs admin).
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from fastapi import HTTPException, status

from app.schemas.properties import ModerationStatus
from app.schemas.users import UserResponse, UserRole
from app.models.properties import Property


TransitionKey = Tuple[str, str]

ROLE_AGENT_OWNS = "agent_owns"
ROLE_AGENCY_OWNER_OF_LISTING = "agency_owner_of_listing"
ROLE_ADMIN = "admin"


# Legal Phase M moderation transitions.
# Keys are (from_status, to_status) pairs using the enum value strings.
LEGAL_TRANSITIONS: Dict[TransitionKey, str] = {
    ("draft", "agency_review"): ROLE_AGENT_OWNS,
    ("draft", "admin_review"): ROLE_AGENCY_OWNER_OF_LISTING,
    ("agency_review", "admin_review"): ROLE_AGENCY_OWNER_OF_LISTING,
    ("agency_review", "agency_rejected"): ROLE_AGENCY_OWNER_OF_LISTING,
    ("agency_review", "draft"): ROLE_AGENT_OWNS,  # withdraw
    ("agency_rejected", "agency_review"): ROLE_AGENT_OWNS,  # resubmit
    ("admin_review", "agency_review"): ROLE_AGENCY_OWNER_OF_LISTING,  # recall
    ("admin_review", "live"): ROLE_ADMIN,
    ("admin_review", "admin_rejected"): ROLE_ADMIN,
    ("admin_rejected", "admin_review"): ROLE_ADMIN,  # reinstate
    ("admin_rejected", "draft"): ROLE_AGENT_OWNS,  # agent pull-back to edit & resubmit
    ("live", "revoked"): ROLE_ADMIN,
    ("revoked", "live"): ROLE_ADMIN,  # restore escape hatch
    ("revoked", "draft"): ROLE_AGENT_OWNS,  # agent pull-back to edit & resubmit
}


def _status_value(raw: Any) -> str:
    """Normalize a moderation_status field or enum into its string value."""
    return str(getattr(raw, "value", raw))


def ensure_legal_moderation_transition(
    *,
    property_obj: Property,
    target_status: ModerationStatus,
    current_user: UserResponse,
) -> None:
    """Enforce the central moderation transition matrix.

    Raises:
      - HTTPException 422 if the (from_status, to_status) pair is not legal.
      - HTTPException 403 if the caller does not have authority for that pair.
    """

    from_status = _status_value(getattr(property_obj, "moderation_status", None))
    to_status = target_status.value

    required_role = LEGAL_TRANSITIONS.get((from_status, to_status))
    if required_role is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Illegal moderation status transition",
        )

    # Admin-only transitions.
    if required_role == ROLE_ADMIN:
        # Prefer the canonical enum; fall back to the legacy is_admin flag for
        # extra safety against partial migrations.
        if current_user.user_role != UserRole.ADMIN and not bool(
            getattr(current_user, "is_admin", False)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required for this transition",
            )
        return

    # Agent-owned listing transitions.
    if required_role == ROLE_AGENT_OWNS:
        if current_user.user_role != UserRole.AGENT or getattr(
            property_obj, "user_id", None
        ) != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the owning agent can perform this transition",
            )
        return

    # Agency-owner-of-listing transitions.
    if required_role == ROLE_AGENCY_OWNER_OF_LISTING:
        if current_user.user_role != UserRole.AGENCY_OWNER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an agency owner can perform this transition",
            )

        listing_agency_id = getattr(property_obj, "agency_id", None)
        if listing_agency_id is None or listing_agency_id != current_user.agency_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the owner of the listing's agency can perform this transition",
            )
        return

    # If we ever add new role tokens but forget to implement them, fail closed.
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unrecognized moderation transition role requirement",
    )
