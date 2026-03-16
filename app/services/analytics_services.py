# app/services/analytics_services.py

"""
Analytics Services - Enhanced with View-Based Queries
Uses pre-computed DB views for heavy analytics, raw queries for real-time stats.

Architecture:
- Heavy aggregations → Use ORM view models (active_properties, agent_performance)
- Real-time stats → Use raw queries on base tables
- Best of both worlds: speed + flexibility
"""

from typing import Optional, List
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

# Base models
from app.models.users import User
from app.models.profiles import Profile
from app.models.properties import Property
from app.models.inquiries import Inquiry
from app.models.reviews import Review
from app.models.favorites import Favorite
from app.models.locations import Location
from app.models.agent_profiles import AgentProfile

# View models (NEW - for pre-computed analytics)
from app.models.analytics import ActivePropertiesView, AgentPerformanceView

# Response schemas
from app.schemas.stats import (
    SystemStatsResponse,
    UserStatsBreakdown,
    PropertyStatsBreakdown,
    InquiryStatsBreakdown,
    UsageMetricsResponse,
    TimeSeriesMetric,
    DataIntegrityResponse,
    DataIntegrityIssue,
    PropertyEngagementResponse,
    AgentPerformanceResponse
)


class AnalyticsService:
    """
    Service for computing system-wide analytics and statistics.
    Hybrid approach: uses views for heavy queries, raw SQL for real-time data.
    """
    
    
    # VIEW-BASED QUERIES (Pre-computed, Fast)
        
    def get_active_properties(
        self, 
        db: Session,
        skip: int = 0,
        limit: int = 100
    ) -> List[ActivePropertiesView]:
        """
        Get active properties from pre-computed view.
        
        Returns properties with enriched data:
        - Location details
        - Owner information
        - Aggregated metrics (images, amenities, reviews)
        
        Use this for property listings, search results, maps.
        """
        return db.query(ActivePropertiesView).offset(skip).limit(limit).all()
    
    
    def get_active_properties_by_location(
        self,
        db: Session,
        state: str = None,
        city: str = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[ActivePropertiesView]:
        """
        Filter active properties by location using view.
        Faster than joining tables at query time.
        """
        query = db.query(ActivePropertiesView)
        
        if state:
            query = query.filter(ActivePropertiesView.state == state)
        if city:
            query = query.filter(ActivePropertiesView.city == city)
        
        return query.offset(skip).limit(limit).all()
    
    
    def get_featured_properties(
        self,
        db: Session,
        limit: int = 10
    ) -> List[ActivePropertiesView]:
        """
        Get featured properties from view.
        Ideal for homepage hero sections.
        """
        return db.query(ActivePropertiesView).filter(
            ActivePropertiesView.is_featured == True
        ).limit(limit).all()
    
    
    def get_agent_performance_list(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100
    ) -> List[AgentPerformanceView]:
        """
        Get all agent performance metrics from pre-computed view.
        
        Returns agents with:
        - Total/active/sold listings
        - Average rating
        - Review count
        - Agency affiliation
        
        Use this for agent directories, leaderboards.
        """
        return db.query(AgentPerformanceView).offset(skip).limit(limit).all()
    
    
    def get_agent_performance_by_id(
        self,
        db: Session,
        user_id: int
    ) -> Optional[AgentPerformanceView]:
        """
        Get single agent's performance metrics from view.
        Returns None if agent not found or not an agent role.
        """
        return db.query(AgentPerformanceView).filter(
            AgentPerformanceView.user_id == user_id
        ).first()
    
    
    def get_top_agents(
        self,
        db: Session,
        limit: int = 10,
        order_by: str = "total_listings"
    ) -> List[AgentPerformanceView]:
        """
        Get top-performing agents from view.
        
        order_by options:
        - "total_listings" (default)
        - "active_listings"
        - "sold_count"
        - "avg_rating"
        """
        query = db.query(AgentPerformanceView)
        
        if order_by == "total_listings":
            query = query.order_by(desc(AgentPerformanceView.total_listings))
        elif order_by == "active_listings":
            query = query.order_by(desc(AgentPerformanceView.active_listings))
        elif order_by == "sold_count":
            query = query.order_by(desc(AgentPerformanceView.sold_count))
        elif order_by == "avg_rating":
            query = query.order_by(desc(AgentPerformanceView.avg_rating))
        
        return query.limit(limit).all()
    
    
    
    # RAW QUERY ANALYTICS (Real-Time, Flexible)
        
    def get_system_stats(self, db: Session) -> SystemStatsResponse:
        """
        Compute comprehensive system statistics for admin dashboard.
        Uses raw queries for real-time counts (not cached in views).
        """
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        # USER STATISTICS
        total_users = db.scalar(
            select(func.count()).select_from(User).where(User.deleted_at.is_(None))
        ) or 0
        
        user_role_counts = db.execute(
            select(User.user_role, func.count(User.user_id).label('count'))
            .where(User.deleted_at.is_(None))
            .group_by(User.user_role)
        ).all()
        
        users_by_role = {str(row.user_role): row.count for row in user_role_counts}
        
        new_users_week = db.scalar(
            select(func.count()).select_from(User)
            .where(and_(User.deleted_at.is_(None), User.created_at >= week_ago))
        ) or 0
        
        new_users_month = db.scalar(
            select(func.count()).select_from(User)
            .where(and_(User.deleted_at.is_(None), User.created_at >= month_ago))
        ) or 0

        user_stats = UserStatsBreakdown(
            total=total_users,
            by_role=users_by_role,
            new_last_7_days=new_users_week,
            new_last_30_days=new_users_month
        )

        # PROPERTY STATISTICS (can also use view counts for speed)
        total_properties = db.scalar(
            select(func.count()).select_from(Property)
            .where(Property.deleted_at.is_(None))
        ) or 0
        
        verified_properties = db.scalar(
            select(func.count()).select_from(Property)
            .where(and_(Property.deleted_at.is_(None), Property.is_verified == True))
        ) or 0
        
        featured_properties = db.scalar(
            select(func.count()).select_from(Property)
            .where(and_(Property.deleted_at.is_(None), Property.is_featured == True))
        ) or 0
        
        prop_status_counts = db.execute(
            select(Property.listing_status, func.count(Property.property_id).label('count'))
            .where(Property.deleted_at.is_(None))
            .group_by(Property.listing_status)
        ).all()
        
        properties_by_status = {str(row.listing_status): row.count for row in prop_status_counts}
        
        prop_type_counts = db.execute(
            select(Property.property_type_id, func.count(Property.property_id).label('count'))
            .where(Property.deleted_at.is_(None))
            .group_by(Property.property_type_id)
        ).all()
        
        properties_by_type = {str(row.property_type_id): row.count for row in prop_type_counts}
        
        new_properties_week = db.scalar(
            select(func.count()).select_from(Property)
            .where(and_(Property.deleted_at.is_(None), Property.created_at >= week_ago))
        ) or 0
        
        new_properties_month = db.scalar(
            select(func.count()).select_from(Property)
            .where(and_(Property.deleted_at.is_(None), Property.created_at >= month_ago))
        ) or 0

        property_stats = PropertyStatsBreakdown(
            total=total_properties,
            verified=verified_properties,
            unverified=total_properties - verified_properties,
            featured=featured_properties,
            by_status=properties_by_status,
            by_type=properties_by_type,
            new_last_7_days=new_properties_week,
            new_last_30_days=new_properties_month
        )

        # INQUIRY STATISTICS
        total_inquiries = db.scalar(
            select(func.count()).select_from(Inquiry)
            .where(Inquiry.deleted_at.is_(None))
        ) or 0
        
        inquiry_status_counts = db.execute(
            select(Inquiry.inquiry_status, func.count(Inquiry.inquiry_id).label('count'))
            .where(Inquiry.deleted_at.is_(None))
            .group_by(Inquiry.inquiry_status)
        ).all()
        
        inquiries_by_status = {row.inquiry_status: row.count for row in inquiry_status_counts}
        
        new_inquiries_week = db.scalar(
            select(func.count()).select_from(Inquiry)
            .where(and_(Inquiry.deleted_at.is_(None), Inquiry.created_at >= week_ago))
        ) or 0
        
        new_inquiries_month = db.scalar(
            select(func.count()).select_from(Inquiry)
            .where(and_(Inquiry.deleted_at.is_(None), Inquiry.created_at >= month_ago))
        ) or 0

        inquiry_stats = InquiryStatsBreakdown(
            total=total_inquiries,
            by_status=inquiries_by_status,
            new_last_7_days=new_inquiries_week,
            new_last_30_days=new_inquiries_month
        )

        # TOP LOCATIONS (can use view for faster results)
        top_locations_raw = db.execute(
            select(
                Location.state, Location.city,
                func.count(Property.property_id).label('property_count')
            )
            .join(Property, Property.location_id == Location.location_id)
            .where(and_(Property.deleted_at.is_(None), Location.is_active == True))
            .group_by(Location.state, Location.city)
            .order_by(desc('property_count'))
            .limit(5)
        ).all()
        
        top_locations = [
            {"state": loc.state, "city": loc.city, "property_count": loc.property_count}
            for loc in top_locations_raw
        ]

        # FINANCIAL AGGREGATES
        financial_agg = db.execute(
            select(
                func.sum(Property.price).label('total_value'),
                func.avg(Property.price).label('avg_price')
            ).where(Property.deleted_at.is_(None))
        ).first()
        
        total_value = financial_agg.total_value if financial_agg else None
        avg_price = financial_agg.avg_price if financial_agg else None

        return SystemStatsResponse(
            users=user_stats,
            properties=property_stats,
            inquiries=inquiry_stats,
            top_locations=top_locations,
            total_property_value=total_value,
            average_property_price=avg_price,
            generated_at=now
        )

    def get_usage_metrics(self, db: Session) -> UsageMetricsResponse:
        """
        Compute time-series usage metrics for admin monitoring.
        Uses last_login and created_at timestamps to track activity.
        """
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        user_logins = TimeSeriesMetric(
            last_24_hours=db.scalar(
                select(func.count()).select_from(User)
                .where(and_(User.deleted_at.is_(None), User.last_login >= day_ago))
            ) or 0,
            last_7_days=db.scalar(
                select(func.count()).select_from(User)
                .where(and_(User.deleted_at.is_(None), User.last_login >= week_ago))
            ) or 0,
            last_30_days=db.scalar(
                select(func.count()).select_from(User)
                .where(and_(User.deleted_at.is_(None), User.last_login >= month_ago))
            ) or 0
        )

        new_properties = TimeSeriesMetric(
            last_24_hours=db.scalar(
                select(func.count()).select_from(Property)
                .where(and_(Property.deleted_at.is_(None), Property.created_at >= day_ago))
            ) or 0,
            last_7_days=db.scalar(
                select(func.count()).select_from(Property)
                .where(and_(Property.deleted_at.is_(None), Property.created_at >= week_ago))
            ) or 0,
            last_30_days=db.scalar(
                select(func.count()).select_from(Property)
                .where(and_(Property.deleted_at.is_(None), Property.created_at >= month_ago))
            ) or 0
        )

        new_inquiries = TimeSeriesMetric(
            last_24_hours=db.scalar(
                select(func.count()).select_from(Inquiry)
                .where(and_(Inquiry.deleted_at.is_(None), Inquiry.created_at >= day_ago))
            ) or 0,
            last_7_days=db.scalar(
                select(func.count()).select_from(Inquiry)
                .where(and_(Inquiry.deleted_at.is_(None), Inquiry.created_at >= week_ago))
            ) or 0,
            last_30_days=db.scalar(
                select(func.count()).select_from(Inquiry)
                .where(and_(Inquiry.deleted_at.is_(None), Inquiry.created_at >= month_ago))
            ) or 0
        )

        new_users = TimeSeriesMetric(
            last_24_hours=db.scalar(
                select(func.count()).select_from(User)
                .where(and_(User.deleted_at.is_(None), User.created_at >= day_ago))
            ) or 0,
            last_7_days=db.scalar(
                select(func.count()).select_from(User)
                .where(and_(User.deleted_at.is_(None), User.created_at >= week_ago))
            ) or 0,
            last_30_days=db.scalar(
                select(func.count()).select_from(User)
                .where(and_(User.deleted_at.is_(None), User.created_at >= month_ago))
            ) or 0
        )

        return UsageMetricsResponse(
            user_logins=user_logins,
            new_properties=new_properties,
            new_inquiries=new_inquiries,
            new_users=new_users,
            generated_at=now
        )

    def get_data_integrity_report(self, db: Session) -> DataIntegrityResponse:
        """
        Validate audit trail integrity for admin diagnostics.
        Counts records missing required audit fields.
        """
        properties_missing_created_by = db.scalar(
            select(func.count()).select_from(Property)
            .where(and_(Property.deleted_at.is_(None), Property.created_by.is_(None)))
        ) or 0

        users_missing_created_by = db.scalar(
            select(func.count()).select_from(User)
            .where(and_(User.deleted_at.is_(None), User.created_by.is_(None)))
        ) or 0

        soft_deleted_missing_deleted_by = db.scalar(
            select(func.count()).select_from(Property)
            .where(and_(Property.deleted_at.is_not(None), Property.deleted_by.is_(None)))
        ) or 0

        issues = [
            DataIntegrityIssue(
                category="properties",
                issue_type="missing_created_by",
                count=properties_missing_created_by,
                description="Active properties with missing created_by",
                severity="high"
            ),
            DataIntegrityIssue(
                category="users",
                issue_type="missing_created_by",
                count=users_missing_created_by,
                description="Active users with missing created_by",
                severity="high"
            ),
            DataIntegrityIssue(
                category="properties",
                issue_type="missing_deleted_by",
                count=soft_deleted_missing_deleted_by,
                description="Soft-deleted properties with missing deleted_by",
                severity="high"
            ),
        ]

        total_issues = sum(issue.count for issue in issues)
        high_severity_count = sum(
            issue.count for issue in issues if issue.severity == "high"
        )
        health_score = max(0.0, 100.0 - min(100.0, float(total_issues)))

        return DataIntegrityResponse(
            issues=issues,
            total_issues=total_issues,
            high_severity_count=high_severity_count,
            health_score=health_score,
            generated_at=datetime.now(timezone.utc)
        )
    
    
    def get_property_engagement(
        self, 
        db: Session, 
        property_id: int
    ) -> Optional[PropertyEngagementResponse]:
        """
        Get engagement metrics for a specific property.
        Uses raw queries for real-time counts.
        """
        # Verify property exists
        prop = db.scalar(
            select(Property).where(
                and_(Property.property_id == property_id, Property.deleted_at.is_(None))
            )
        )
        
        if not prop:
            return None

        # Count inquiries, favorites, reviews
        inquiry_count = db.scalar(
            select(func.count()).select_from(Inquiry)
            .where(and_(Inquiry.property_id == property_id, Inquiry.deleted_at.is_(None)))
        ) or 0

        favorite_count = db.scalar(
            select(func.count()).select_from(Favorite)
            .where(and_(Favorite.property_id == property_id, Favorite.deleted_at.is_(None)))
        ) or 0

        review_stats = db.execute(
            select(
                func.count(Review.review_id).label('review_count'),
                func.avg(Review.rating).label('avg_rating')
            )
            .where(and_(Review.property_id == property_id, Review.deleted_at.is_(None)))
        ).first()
        
        review_count = review_stats.review_count or 0
        avg_rating = review_stats.avg_rating

        rating_dist_raw = db.execute(
            select(Review.rating, func.count(Review.review_id).label('count'))
            .where(and_(Review.property_id == property_id, Review.deleted_at.is_(None)))
            .group_by(Review.rating)
        ).all()
        
        rating_distribution = {row.rating: row.count for row in rating_dist_raw}
        days_listed = (datetime.now(timezone.utc) - prop.created_at).days

        return PropertyEngagementResponse(
            property_id=property_id,
            inquiry_count=inquiry_count,
            favorite_count=favorite_count,
            review_count=review_count,
            average_rating=avg_rating,
            rating_distribution=rating_distribution,
            days_listed=days_listed,
            is_featured=prop.is_featured,
            is_verified=prop.is_verified
        )


# Singleton instance
analytics_service = AnalyticsService()
