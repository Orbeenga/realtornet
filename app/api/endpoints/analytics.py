# app/api/endpoints/analytics.py
"""
Analytics API Endpoints
Location: app/api/endpoints/analytics.py

Exposes analytics views and computed statistics with security hardening:
- RLS enforcement via get_current_active_user
- Request size validation
- Rate limiting ready
- DoS protection via Pydantic validation
- No stack trace leakage in production

Routes:
- GET /analytics/properties/active - Active property listings (view-based)
- GET /analytics/properties/featured - Featured properties (view-based)
- GET /analytics/agents/performance - Agent performance metrics (view-based)
- GET /analytics/agents/{user_id} - Single agent performance
- GET /analytics/agents/top - Top performing agents
- GET /analytics/system/stats - System-wide statistics (computed)
- GET /analytics/system/usage - Usage metrics (computed)
- GET /analytics/system/integrity - Data integrity report (admin only)
- GET /analytics/properties/{property_id}/engagement - Property engagement
"""

from typing import Dict, List, Optional
from sqlalchemy import select, func, and_
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

# --- CANONICAL IMPORTS ---
from app.core.database import get_db
from app.api.dependencies import (
    get_current_active_user, 
    get_current_admin_user,  # Replaces require_role
    validate_request_size
)
from app.models.users import User as User
from app.services.analytics_services import analytics_service
from app.models.analytics import ActivePropertiesView, AgentPerformanceView
from app.models.properties import Property
from app.models.property_types import PropertyType
from app.models.inquiries import Inquiry, InquiryStatus
from app.models.inquiry_replies import InquiryReply
from app.models.agency_join_requests import AgencyAgentMembership
from app.models.agencies import Agency
from app.schemas.stats import (
    SystemStatsResponse,
    UsageMetricsResponse,
    DataIntegrityResponse,
    PropertyEngagementResponse,
    AgentStatsResponse,
    AgentListingsByStatusResponse,
    AgentListingStatusCount,
    AgentListingStatusItem,
    AgentInquiryResponseRateResponse,
    AgentInquiryResponseDetail,
    AgentMembershipsResponse,
    AgentMembershipDetail,
)
from app.schemas.users import UserResponse

# Lightweight response schemas for views (avoid heavy Pydantic overhead)
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from datetime import datetime

# RESPONSE SCHEMAS (View-based endpoints)
class ActivePropertyResponse(BaseModel):
    """Lightweight response schema for active_properties view"""
    property_id: int
    title: str
    description: Optional[str] = None
    price: Optional[Decimal] = None
    price_currency: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[Decimal] = None
    property_size: Optional[Decimal] = None
    listing_status: Optional[str] = None
    is_featured: bool = False
    is_verified: bool = False
    
    # LocationResponse data
    state: Optional[str] = None
    city: Optional[str] = None
    neighborhood: Optional[str] = None
    property_type_name: Optional[str] = None
    
    # Owner info
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    
    # Aggregated metrics
    image_count: int = 0
    amenity_count: int = 0
    review_count: int = 0
    avg_rating: Optional[Decimal] = None
    
    created_at: datetime
    
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: lambda v: float(v) if v else None}
    )

class AgentPerformanceResponse(BaseModel):
    """Lightweight response schema for agent_performance view"""
    user_id: int
    agent_name: str
    license_number: Optional[str] = None
    agency_name: Optional[str] = None
    total_listings: int = 0
    active_listings: int = 0
    sold_count: int = 0
    avg_rating: Optional[Decimal] = None
    review_count: int = 0
    
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: lambda v: float(v) if v else None}
    )

# ROUTER SETUP
router = APIRouter(
    responses={
        401: {"description": "Unauthorized - Authentication required"},
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Not found"},
        429: {"description": "Too many requests - Rate limit exceeded"}
    }
)

# VIEW-BASED ENDPOINTS (Fast, Pre-computed)

@router.get(
    "/properties/active",
    response_model=List[ActivePropertyResponse],
    summary="Get active property listings",
    description="Returns active properties from pre-computed view with location, owner, and engagement metrics"
)
async def get_active_properties(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    state: Optional[str] = Query(None, description="Filter by state"),
    city: Optional[str] = Query(None, description="Filter by city"),
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_active_user)
):
    """
    Get active property listings with enriched data.

    Security:
    - Requires authenticated active user
    - RLS applied via security_invoker view
    - Results filtered by user's permissions

    Performance: Uses pre-computed view (~50ms vs 500ms)
    """
    try:
        if state or city:
            properties = analytics_service.get_active_properties_by_location(
                db, state=state, city=city, skip=skip, limit=limit
            )
        else:
            properties = analytics_service.get_active_properties(
                db, skip=skip, limit=limit
            )
        return properties
    except Exception:
        # No stack trace in production
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve active properties"
        )

@router.get(
    "/properties/featured",
    response_model=List[ActivePropertyResponse],
    summary="Get featured properties",
    description="Returns featured properties for homepage/hero sections"
)
async def get_featured_properties(
    limit: int = Query(10, ge=1, le=50, description="Maximum featured properties"),
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_active_user)
):
    """
    Get featured properties from view.
    
    Security: RLS enforced, requires active authenticated user
    Performance: Pre-computed view with featured flag filter
    """
    try:
        properties = analytics_service.get_featured_properties(db, limit=limit)
        return properties
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve featured properties"
        )

@router.get(
    "/agents/performance",
    response_model=List[AgentPerformanceResponse],
    summary="Get agent performance metrics",
    description="Returns agent performance data with listing stats and ratings"
)
async def get_agent_performance(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_active_user)
):
    """
    Get agent performance metrics from pre-computed view.
    
    Security: RLS enforced via security_invoker
    Performance: ~30ms response time
    """
    try:
        agents = analytics_service.get_agent_performance_list(
            db, skip=skip, limit=limit
        )
        return agents
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve agent performance data"
        )

@router.get(
    "/agents/top",
    response_model=List[AgentPerformanceResponse],
    summary="Get top performing agents",
    description="Returns top agents ranked by listings, sales, or rating"
)
async def get_top_agents(
    limit: int = Query(10, ge=1, le=50, description="Number of top agents"),
    order_by: str = Query(
        "total_listings",
        description="Ranking criteria",
        pattern="^(total_listings|active_listings|sold_count|avg_rating)$"
    ),
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_active_user)
):
    """
    Get top performing agents from view.
    
    Order by options:
    - total_listings (default)
    - active_listings
    - sold_count
    - avg_rating
    
    Security: RLS enforced, results filtered by permissions
    """
    try:
        agents = analytics_service.get_top_agents(
            db, limit=limit, order_by=order_by
        )
        return agents
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve top agents"
        )

@router.get(
    "/agents/me/stats",
    response_model=AgentStatsResponse,
    summary="Get personal agent stats",
    description="Returns personal listing breakdown, inquiry counts, and membership stats for the current agent or agency_owner."
)
async def get_agent_personal_stats(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_active_user),
):
    user_id = current_user.user_id

    # Listings by moderation_status
    listing_counts = list(
        db.execute(
            select(Property.moderation_status, func.count().label("cnt"))
            .where(
                and_(
                    Property.user_id == user_id,
                    Property.deleted_at.is_(None),
                )
            )
            .group_by(Property.moderation_status)
        ).all()
    )
    listings_by_status: Dict[str, int] = {}
    for row in listing_counts:
        status_val = row.moderation_status.value
        listings_by_status[status_val] = int(row.cnt)

    # Inquiries received for user's properties
    total_inquiries = db.scalar(
        select(func.count())
        .select_from(Inquiry)
        .join(Property, Inquiry.property_id == Property.property_id)
        .where(
            and_(
                Property.user_id == user_id,
                Inquiry.deleted_at.is_(None),
                Property.deleted_at.is_(None),
            )
        )
    ) or 0

    inquiries_responded = db.scalar(
        select(func.count())
        .select_from(Inquiry)
        .join(Property, Inquiry.property_id == Property.property_id)
        .where(
            and_(
                Property.user_id == user_id,
                Inquiry.inquiry_status == "responded",
                Inquiry.deleted_at.is_(None),
                Property.deleted_at.is_(None),
            )
        )
    ) or 0

    response_rate = round(inquiries_responded / total_inquiries * 100, 1) if total_inquiries > 0 else 0.0

    # Membership counts
    membership_rows = list(
        db.execute(
            select(AgencyAgentMembership.status, func.count().label("cnt"))
            .where(
                and_(
                    AgencyAgentMembership.user_id == user_id,
                    AgencyAgentMembership.deleted_at.is_(None),
                )
            )
            .group_by(AgencyAgentMembership.status)
        ).all()
    )
    membership_counts: Dict[str, int] = {}
    for row in membership_rows:
        membership_counts[str(row.status)] = int(row.cnt)

    return AgentStatsResponse(
        user_id=user_id,
        listings_by_status=listings_by_status,
        total_inquiries_received=total_inquiries,
        inquiries_responded=inquiries_responded,
        response_rate=response_rate,
        membership_counts=membership_counts,
    )


@router.get(
    "/agents/me/stats/listings-by-status",
    response_model=AgentListingsByStatusResponse,
    summary="Get personal listings drill-down",
    description="Returns listing counts by moderation status plus itemized listings for the current agent.",
)
async def get_agent_listings_by_status(
    status: Optional[str] = Query(None, description="Filter by moderation_status value"),
    pending_only: bool = Query(False, description="When true, exclude live listings"),
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_active_user),
):
    user_id = current_user.user_id

    listing_counts = list(
        db.execute(
            select(Property.moderation_status, func.count().label("cnt"))
            .where(
                and_(
                    Property.user_id == user_id,
                    Property.deleted_at.is_(None),
                )
            )
            .group_by(Property.moderation_status)
        ).all()
    )
    statuses = [
        AgentListingStatusCount(status=row.moderation_status.value, count=int(row.cnt))
        for row in listing_counts
    ]

    listing_query = (
        select(
            Property.property_id,
            Property.title,
            Property.moderation_status,
            Property.created_at,
            PropertyType.name.label("property_type_name"),
        )
        .outerjoin(PropertyType, Property.property_type_id == PropertyType.property_type_id)
        .where(
            and_(
                Property.user_id == user_id,
                Property.deleted_at.is_(None),
            )
        )
        .order_by(Property.created_at.desc())
    )
    if status:
        listing_query = listing_query.where(Property.moderation_status == status)
    if pending_only:
        listing_query = listing_query.where(Property.moderation_status != "live")

    listing_rows = list(db.execute(listing_query).all())
    items = [
        AgentListingStatusItem(
            property_id=row.property_id,
            property_type=row.property_type_name,
            moderation_status=row.moderation_status.value,
            title=row.title,
            created_at=row.created_at,
        )
        for row in listing_rows
    ]

    return AgentListingsByStatusResponse(
        count=len(items),
        statuses=statuses,
        items=items,
    )


@router.get(
    "/agents/me/stats/inquiry-response-rate",
    response_model=AgentInquiryResponseRateResponse,
    summary="Get personal inquiry response drill-down",
    description="Returns inquiry response aggregates and per-inquiry details for the current agent.",
)
async def get_agent_inquiry_response_rate(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_active_user),
):
    user_id = current_user.user_id

    inquiry_rows = list(
        db.execute(
            select(
                Inquiry.inquiry_id,
                Inquiry.property_id,
                Inquiry.inquiry_status,
                Inquiry.created_at,
                Property.title.label("property_title"),
                func.min(InquiryReply.created_at).label("first_reply_at"),
            )
            .join(Property, Inquiry.property_id == Property.property_id)
            .outerjoin(InquiryReply, InquiryReply.inquiry_id == Inquiry.inquiry_id)
            .where(
                and_(
                    Property.user_id == user_id,
                    Inquiry.deleted_at.is_(None),
                    Property.deleted_at.is_(None),
                )
            )
            .group_by(
                Inquiry.inquiry_id,
                Inquiry.property_id,
                Inquiry.inquiry_status,
                Inquiry.created_at,
                Property.title,
            )
            .order_by(Inquiry.created_at.desc())
        ).all()
    )

    details: List[AgentInquiryResponseDetail] = []
    responded_count = 0
    for row in inquiry_rows:
        responded = row.inquiry_status == InquiryStatus.responded
        if responded:
            responded_count += 1
        response_time_minutes: Optional[int] = None
        if responded and row.first_reply_at and row.created_at:
            delta = row.first_reply_at - row.created_at
            response_time_minutes = max(0, int(delta.total_seconds() // 60))
        details.append(
            AgentInquiryResponseDetail(
                inquiry_id=row.inquiry_id,
                property_id=row.property_id,
                property_title=row.property_title,
                responded=responded,
                response_time_minutes=response_time_minutes,
                created_at=row.created_at,
            )
        )

    total_inquiries = len(details)
    unresponded = total_inquiries - responded_count
    rate = round(responded_count / total_inquiries, 4) if total_inquiries > 0 else 0.0

    return AgentInquiryResponseRateResponse(
        rate=rate,
        period="all_time",
        total_inquiries=total_inquiries,
        responded=responded_count,
        unresponded=unresponded,
        details=details,
    )


@router.get(
    "/agents/me/stats/agency-memberships",
    response_model=AgentMembershipsResponse,
    summary="Get personal agency membership drill-down",
    description="Returns agency membership counts and roster details for the current agent.",
)
async def get_agent_agency_memberships(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_active_user),
):
    user_id = current_user.user_id

    membership_rows = list(
        db.execute(
            select(
                AgencyAgentMembership.membership_id,
                AgencyAgentMembership.user_id,
                AgencyAgentMembership.agency_id,
                AgencyAgentMembership.status,
                AgencyAgentMembership.created_at,
                Agency.name.label("agency_name"),
            )
            .join(Agency, AgencyAgentMembership.agency_id == Agency.agency_id)
            .where(
                and_(
                    AgencyAgentMembership.user_id == user_id,
                    AgencyAgentMembership.deleted_at.is_(None),
                    Agency.deleted_at.is_(None),
                )
            )
            .order_by(AgencyAgentMembership.created_at.desc())
        ).all()
    )

    memberships = [
        AgentMembershipDetail(
            membership_id=row.membership_id,
            user_id=row.user_id,
            agency_id=row.agency_id,
            agency_name=row.agency_name,
            role=current_user.user_role.value,
            joined_at=row.created_at,
            status=str(row.status),
        )
        for row in membership_rows
    ]

    return AgentMembershipsResponse(
        count=len(memberships),
        memberships=memberships,
    )


@router.get(
    "/agents/{user_id}",
    response_model=AgentPerformanceResponse,
    summary="Get single agent performance",
    description="Returns performance metrics for specific agent"
)
async def get_agent_performance_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_active_user)
):
    """
    Get performance metrics for a specific agent.
    
    Security: RLS applied, user can only see agents they have permission for
    """
    agent = analytics_service.get_agent_performance_by_id(db, user_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with user_id {user_id} not found"
        )
    return agent

# COMPUTED ANALYTICS ENDPOINTS (Admin Only)

@router.get(
    "/system/stats",
    response_model=SystemStatsResponse,
    summary="Get system-wide statistics",
    description="Comprehensive system statistics for admin dashboard"
)
async def get_system_stats(
    db: Session = Depends(get_db),
    # Use explicit admin dependency instead of require_role helper
    current_user: UserResponse = Depends(get_current_admin_user)
):
    """
    Get comprehensive system statistics.
    
    Security: Admin only
    Performance: Real-time computation (~100ms)
    
    Returns:
    - User statistics (total, by role, growth)
    - Property statistics (total, verified, featured, by status/type)
    - Inquiry statistics (total, by status, growth)
    - Top locations
    - Financial aggregates
    """
    try:
        stats = analytics_service.get_system_stats(db)
        return stats
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute system statistics"
        )

@router.get(
    "/system/usage",
    response_model=UsageMetricsResponse,
    summary="Get usage metrics",
    description="Time-series usage metrics for system monitoring"
)
async def get_usage_metrics(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_admin_user)
):
    """
    Get time-series usage metrics.
    
    Security: Admin only
    
    Returns metrics for:
    - User logins (24h, 7d, 30d)
    - New properties (24h, 7d, 30d)
    - New inquiries (24h, 7d, 30d)
    - New users (24h, 7d, 30d)
    """
    try:
        metrics = analytics_service.get_usage_metrics(db)
        return metrics
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute usage metrics"
        )

@router.get(
    "/system/integrity",
    response_model=DataIntegrityResponse,
    summary="Get data integrity report",
    description="Data quality and integrity health check (admin only)"
)
async def get_data_integrity_report(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_admin_user)
):
    """
    Get data integrity and quality report.
    
    Security: Admin only (diagnostic tool)
    
    Checks for:
    - Incomplete records
    - Orphaned data
    - Invalid references
    - Data quality issues
    
    Returns health score and detailed issue list.
    """
    try:
        report = analytics_service.get_data_integrity_report(db)
        return report
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate integrity report"
        )

@router.get(
    "/properties/{property_id}/engagement",
    response_model=PropertyEngagementResponse,
    summary="Get property engagement metrics",
    description="Engagement metrics for a specific property"
)
async def get_property_engagement(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_active_user)
):
    """
    Get engagement metrics for a specific property.
    
    Security: RLS enforced, user can only see properties they have access to
    
    Returns:
    - Inquiry count
    - Favorite count
    - ReviewResponse count and distribution
    - Average rating
    - Days listed
    - Featured/verified status
    """
    engagement = analytics_service.get_property_engagement(db, property_id)
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property with ID {property_id} not found"
        )
    return engagement
