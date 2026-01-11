# app/schemas/stats.py

"""
Pydantic schemas for system statistics and analytics.
These are computed aggregations, not direct DB table mappings.
Use for dashboard/analytics endpoints that compute stats on-demand.

Enhanced with usage metrics, data integrity, and comprehensive system health.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from decimal import Decimal


# SYSTEM-WIDE STATISTICS

class UserStatsBreakdown(BaseModel):
    """Detailed user statistics breakdown"""
    total: int
    by_role: Dict[str, int] = Field(default_factory=dict)  # {"seeker": X, "agent": Y, "admin": Z}
    new_last_7_days: int = 0
    new_last_30_days: int = 0
    
    model_config = ConfigDict(from_attributes=True)


class PropertyStatsBreakdown(BaseModel):
    """Detailed property statistics breakdown"""
    total: int
    verified: int = 0
    unverified: int = 0
    featured: int = 0
    by_status: Dict[str, int] = Field(default_factory=dict)  # {"available": X, "sold": Y, ...}
    by_type: Dict[str, int] = Field(default_factory=dict)    # {"apartment": X, "house": Y, ...}
    new_last_7_days: int = 0
    new_last_30_days: int = 0
    
    model_config = ConfigDict(from_attributes=True)


class InquiryStatsBreakdown(BaseModel):
    """Detailed inquiry statistics breakdown"""
    total: int
    by_status: Dict[str, int] = Field(default_factory=dict)  # {"new": X, "viewed": Y, "responded": Z}
    new_last_7_days: int = 0
    new_last_30_days: int = 0
    
    model_config = ConfigDict(from_attributes=True)


class SystemStatsResponse(BaseModel):
    """
    Comprehensive system statistics for admin dashboards.
    Computed from multiple tables with proper soft-delete filtering.
    """
    users: UserStatsBreakdown
    properties: PropertyStatsBreakdown
    inquiries: InquiryStatsBreakdown
    
    # Top locations by property count
    top_locations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top 5 locations by property count"
    )
    
    # Financial aggregates
    total_property_value: Optional[Decimal] = None
    average_property_price: Optional[Decimal] = None
    
    # Timestamp when stats were generated
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            Decimal: lambda v: float(v) if v else None
        }
    )


# USAGE METRICS (Time-Series)

class TimeSeriesMetric(BaseModel):
    """Generic time-series metric structure"""
    last_24_hours: int = 0
    last_7_days: int = 0
    last_30_days: int = 0
    
    model_config = ConfigDict(from_attributes=True)


class UsageMetricsResponse(BaseModel):
    """
    System usage metrics over time.
    Tracks user activity, content creation, and engagement.
    """
    # User activity (requires last_login tracking)
    user_logins: TimeSeriesMetric
    
    # Content creation
    new_properties: TimeSeriesMetric
    new_inquiries: TimeSeriesMetric
    
    # User registration
    new_users: TimeSeriesMetric
    
    # Timestamp when metrics were computed
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = ConfigDict(from_attributes=True)


# DATA INTEGRITY & HEALTH

class DataIntegrityIssue(BaseModel):
    """Single data integrity issue detail"""
    category: str  # "users", "properties", "relationships"
    issue_type: str  # "incomplete", "orphaned", "invalid"
    count: int
    description: str
    severity: str = "medium"  # "low", "medium", "high"
    
    model_config = ConfigDict(from_attributes=True)


class DataIntegrityResponse(BaseModel):
    """
    Data quality and integrity health check.
    Identifies incomplete records, orphaned data, and referential issues.
    """
    issues: List[DataIntegrityIssue] = Field(default_factory=list)
    
    # Summary counts
    total_issues: int = 0
    high_severity_count: int = 0
    
    # Health score (0-100, higher is better)
    health_score: Optional[float] = None
    
    # Timestamp when check was performed
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = ConfigDict(from_attributes=True)


# LOCATION-BASED STATISTICS

class LocationStatsResponse(BaseModel):
    """
    Location-based property market statistics.
    Computed from properties + locations tables.
    """
    location_id: int
    state: str
    city: Optional[str] = None
    neighborhood: Optional[str] = None
    
    # Market metrics
    property_count: int = 0
    active_listings: int = 0
    average_price: Optional[Decimal] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    
    # Market activity
    new_listings_30_days: Optional[int] = 0
    
    # Price trends (requires historical data)
    price_change_30_days: Optional[float] = None  # Percentage change
    
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            Decimal: lambda v: float(v) if v else None
        }
    )


class LocationStatsListResponse(BaseModel):
    """Paginated list of location statistics"""
    locations: List[LocationStatsResponse]
    total: int
    page: int = 1
    page_size: int = 50

    model_config = ConfigDict(from_attributes=True)


# PROPERTY ENGAGEMENT STATISTICS

class PropertyEngagementResponse(BaseModel):
    """
    Property-specific engagement metrics.
    Computed from inquiries, favorites, reviews.
    """
    property_id: int
    
    # Engagement counts
    inquiry_count: int = 0
    favorite_count: int = 0
    review_count: int = 0
    
    # Rating metrics
    average_rating: Optional[Decimal] = None
    rating_distribution: Dict[int, int] = Field(
        default_factory=dict,
        description="Distribution of ratings (1-5 stars)"
    )
    
    # Listing metrics
    days_listed: int = 0
    is_featured: bool = False
    is_verified: bool = False
    
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            Decimal: lambda v: float(v) if v else None
        }
    )


# AGENT PERFORMANCE STATISTICS

class AgentPerformanceResponse(BaseModel):
    """
    Agent-specific performance metrics.
    Tracks listings, inquiries, and client engagement.
    """
    user_id: int
    agent_profile_id: Optional[int] = None
    
    # Listing metrics
    total_properties: int = 0
    active_listings: int = 0
    verified_properties: int = 0
    
    # Engagement metrics
    total_inquiries_received: int = 0
    inquiries_responded: int = 0
    response_rate: Optional[float] = None  # Percentage
    
    # Review metrics
    review_count: int = 0
    average_rating: Optional[Decimal] = None
    
    # Performance period
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            Decimal: lambda v: float(v) if v else None
        }
    )


# FUTURE/PLACEHOLDER SCHEMAS

class UserActivityStatsResponse(BaseModel):
    """
    User activity metrics (requires activity tracking).
    Placeholder for future implementation with event logging.
    """
    user_id: int
    
    # Activity counts (requires tracking infrastructure)
    properties_viewed: int = 0
    searches_performed: int = 0
    inquiries_sent: int = 0
    properties_saved: int = 0
    reviews_written: int = 0
    
    # Temporal data
    last_active: Optional[datetime] = None
    account_age_days: int = 0
    
    model_config = ConfigDict(from_attributes=True)