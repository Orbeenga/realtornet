"""Saved-search match notification orchestration."""

from decimal import Decimal
from typing import Any, cast

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.crud.saved_searches import saved_search as saved_search_crud
from app.models.properties import Property
from app.models.property_images import PropertyImage
from app.tasks.email_tasks import dispatch_email_task, send_saved_search_match_email


def _primary_thumbnail_url(db: Session, *, property_id: int) -> str | None:
    stmt = (
        select(PropertyImage.image_url)
        .where(PropertyImage.property_id == property_id)
        .order_by(desc(PropertyImage.is_primary), PropertyImage.display_order.asc(), PropertyImage.image_id.asc())
        .limit(1)
    )
    value = db.execute(stmt).scalar_one_or_none()
    return str(value).strip() if value else None


def _price_label(value: Any, currency: str | None) -> str:
    price = Decimal(str(value))
    return f"{currency or 'NGN'} {price:,.2f}"


def notify_saved_search_matches_for_property(db: Session, *, property_obj: Property) -> int:
    """
    Dispatch saved-search match emails for a newly verified listing.

    The match detector batches saved-search/user loading; this service adds a
    single thumbnail lookup and then fail-open transactional email dispatch.
    """
    property_id = cast(int, property_obj.property_id)
    thumbnail_url = _primary_thumbnail_url(db, property_id=property_id)
    matches = saved_search_crud.find_matches_for_verified_property(db, property_obj=property_obj)
    for match in matches:
        dispatch_email_task(
            send_saved_search_match_email,
            match.user_email,
            match.search_name,
            str(property_obj.title),
            _price_label(property_obj.price, cast(str | None, property_obj.price_currency)),
            property_id,
            str(match.unsubscribe_token),
            thumbnail_url,
        )
    return len(matches)
