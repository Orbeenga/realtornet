"""Agency inquiry aggregation queries."""

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, joinedload

from app.models.agency_join_requests import AgencyAgentMembership
from app.models.inquiries import Inquiry
from app.models.properties import Property


def get_agency_inquiries(
    db: Session,
    *,
    agency_id: int,
    skip: int = 0,
    limit: int = 20,
) -> list[Inquiry]:
    """Return inquiries for listings owned by active agency members."""
    stmt = (
        select(Inquiry)
        .options(
            joinedload(Inquiry.user),
            joinedload(Inquiry.property).joinedload(Property.agency),
        )
        .join(Property, Inquiry.property_id == Property.property_id)
        .join(
            AgencyAgentMembership,
            and_(
                AgencyAgentMembership.agency_id == agency_id,
                AgencyAgentMembership.user_id == Property.user_id,
                AgencyAgentMembership.status == "active",
                AgencyAgentMembership.deleted_at.is_(None),
            ),
        )
        .where(
            Inquiry.deleted_at.is_(None),
            Property.deleted_at.is_(None),
        )
        .order_by(Inquiry.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())
