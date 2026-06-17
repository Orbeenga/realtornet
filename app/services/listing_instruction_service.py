"""Instruction mediation service (Phase N N.1).

Provides helpers for writing and querying listing_instructions rows, and
for determining instruction status for CTA gating on revoked/rejected listings.
"""

from typing import Any, cast as type_cast

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, cast, func, or_, String

from app.models.listing_instructions import ListingInstruction
from app.models.listing_events import ListingEvent
from app.models.properties import Property


def write_instruction(
    db: Session,
    *,
    listing_id: int,
    agency_id: int,
    actor_id: int,
    triggered_by_event_id: int,
    instruction_text: str,
) -> ListingInstruction:
    """Write a listing_instructions row."""
    instruction = ListingInstruction(
        listing_id=listing_id,
        agency_id=agency_id,
        actor_id=actor_id,
        triggered_by_event_id=triggered_by_event_id,
        instruction_text=instruction_text,
    )
    db.add(instruction)
    db.flush()
    db.refresh(instruction)
    return instruction


def get_most_relevant_rejection_event(
    db: Session,
    *,
    listing_id: int,
) -> ListingEvent | None:
    """Get the most recent listing_events row where to_status IN ('revoked', 'admin_rejected').

    Excludes communication-only events (e.g., 'Agency instruction written') so that
    the most recent true enforcement action is always used for CTA gating.
    """
    # Use SQL-level comparisons — PGEnum returns enum members on read;
    # Python 3.12+ str(enum_member) gives the name ('ModerationStatus.revoked'),
    # not the value ('revoked'), so .value must be used for string comparison.
    # SQLAlchemy's PGEnum handles the SQL-side value comparison correctly.
    return (
        db.query(ListingEvent)
        .filter(
            ListingEvent.listing_id == listing_id,
            or_(
                ListingEvent.to_status == "revoked",
                ListingEvent.to_status == "admin_rejected",
            ),
            ListingEvent.reason != "Agency instruction written",
        )
        .order_by(desc(ListingEvent.created_at), desc(ListingEvent.event_id))
        .first()
    )


def get_active_instruction_for_event(
    db: Session,
    *,
    listing_id: int,
    triggered_by_event_id: int,
) -> ListingInstruction | None:
    """Check if an instruction exists for the specific revocation/rejection event."""
    return (
        db.query(ListingInstruction)
        .filter(
            ListingInstruction.listing_id == listing_id,
            ListingInstruction.triggered_by_event_id == triggered_by_event_id,
        )
        .first()
    )


def get_instruction_status(
    db: Session,
    *,
    listing_id: int,
) -> tuple[bool, str | None]:
    """Return (has_instruction, instruction_text) for this listing based on the most recent event."""
    most_recent_event = get_most_relevant_rejection_event(db, listing_id=listing_id)
    if not most_recent_event:
        return (False, None)

    event_id_val: int = int(type_cast(Any, most_recent_event).event_id)
    instruction = get_active_instruction_for_event(
        db, listing_id=listing_id, triggered_by_event_id=event_id_val
    )
    if instruction:
        return (True, str(type_cast(Any, instruction).instruction_text))
    return (False, None)


def get_most_recent_event_reason(
    db: Session,
    *,
    listing_id: int,
) -> str | None:
    """Get the reason from the most recent revocation or rejection event."""
    event = get_most_relevant_rejection_event(db, listing_id=listing_id)
    if event:
        return str(type_cast(Any, event).reason) if type_cast(Any, event).reason else None
    return None


def get_listing_instructions(
    db: Session,
    *,
    listing_id: int,
) -> list[ListingInstruction]:
    """Get all instructions for a listing, ordered by created_at ascending."""
    return (
        db.query(ListingInstruction)
        .options(joinedload(ListingInstruction.actor))
        .filter(ListingInstruction.listing_id == listing_id)
        .order_by(ListingInstruction.created_at.asc())
        .all()
    )


def enrich_property_with_instruction_fields(
    db: Session,
    *,
    property_obj: Property,
    current_user_id: int,
    current_user_role: str | None = None,
    current_user_agency_id: int | None = None,
    force_has_instruction: bool | None = None,
    force_instruction_text: str | None = None,
) -> None:
    """Populate has_instruction, instruction_text, and latest_event_reason on a Property ORM object.

    These fields are read by PropertyResponse (from_attributes=True) for response serialization.
    - has_instruction / instruction_text: set for the listing creator, agency_owner of the listing,
      or via force_* params
    - latest_event_reason: set for listing creator, agency_owner, and admin roles

    The force_* parameters are used by the instruct endpoint which needs to set
    these fields after writing a new instruction (the actor is agency_owner, not creator).
    """
    prop_id: int = int(type_cast(Any, property_obj).property_id)
    prop_agency_id: int | None = getattr(property_obj, "agency_id", None)

    # Normalize current_user_role — Python 3.12+ str(enum) returns the name
    # (e.g. 'UserRole.AGENT'), not the value ('agent'), so extract .value.
    import enum as _enum_mod
    role_value: str | None = (
        current_user_role.value
        if isinstance(current_user_role, _enum_mod.Enum)
        else (current_user_role or "")
    )

    is_creator = getattr(property_obj, "user_id", None) == current_user_id
    is_agency_owner_for_listing = (
        role_value == "agency_owner"
        and prop_agency_id is not None
        and current_user_agency_id is not None
        and prop_agency_id == current_user_agency_id
    )

    if force_has_instruction is not None:
        type_cast(Any, property_obj).has_instruction = force_has_instruction
        type_cast(Any, property_obj).instruction_text = force_instruction_text
    elif is_creator or is_agency_owner_for_listing:
        has_instruction, instruction_text = get_instruction_status(db, listing_id=prop_id)
        type_cast(Any, property_obj).has_instruction = has_instruction
        type_cast(Any, property_obj).instruction_text = instruction_text

    if role_value in ("agent", "agency_owner", "admin") or force_has_instruction is not None:
        reason = get_most_recent_event_reason(db, listing_id=prop_id)
        type_cast(Any, property_obj).latest_event_reason = reason


def check_instruction_gate(
    db: Session,
    *,
    property_obj: Property,
) -> None:
    """Raise HTTPException 422 if the listing is revoked/admin_rejected without an active instruction.

    Used by edit (PUT) and pull-back endpoints to enforce the instruction mediation gate.
    """
    from fastapi import HTTPException

    status_raw = getattr(property_obj, "moderation_status", None)
    status_str = str(getattr(status_raw, "value", status_raw)) if status_raw is not None else ""

    if status_str not in ("revoked", "admin_rejected"):
        return

    has_instruction, _ = get_instruction_status(db, listing_id=int(type_cast(Any, property_obj).property_id))
    if not has_instruction:
        raise HTTPException(
            status_code=422,
            detail="Await agency instruction before resubmitting.",
        )
