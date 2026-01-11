# app/api/api.py
"""
RealtorNet API Router - Central routing configuration.
Phase 2 Aligned: Complete domain coverage, consistent naming, logical organization

All routes are prefixed with /api/realtornet/v1 via settings.
Router organization: Auth → Core Entities → Domain Entities → Relationships
"""

from fastapi import APIRouter

from app.api.endpoints import (
    # Authentication & Authorization
    auth,
    admin,
    
    # Core Entities
    users,
    agencies,
    agent_profiles,
    profiles,
    
    # Domain Entities
    locations,
    properties,
    property_types,
    amenities,
    
    # Relationships & Interactions
    property_amenities,
    property_images,
    favorites,
    saved_searches,
    inquiries,
    reviews,
)

api_router = APIRouter()


# AUTHENTICATION & AUTHORIZATION

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["auth"]
)

api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"]
)


# CORE ENTITIES (Users, Agencies, Profiles)

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["users"]
)

api_router.include_router(
    agencies.router,
    prefix="/agencies",
    tags=["agencies"]
)

api_router.include_router(
    agent_profiles.router,
    prefix="/agent-profiles",
    tags=["agent-profiles"]
)

api_router.include_router(
    profiles.router,
    prefix="/profiles",
    tags=["profiles"]
)


# DOMAIN ENTITIES (Properties, Locations, Types, Amenities)

api_router.include_router(
    locations.router,
    prefix="/locations",
    tags=["locations"]
)

api_router.include_router(
    properties.router,
    prefix="/properties",
    tags=["properties"]
)

api_router.include_router(
    property_types.router,
    prefix="/property-types",
    tags=["property-types"]
)

api_router.include_router(
    amenities.router,
    prefix="/amenities",
    tags=["amenities"]
)


# RELATIONSHIPS & INTERACTIONS

api_router.include_router(
    property_amenities.router,
    prefix="/property-amenities",
    tags=["property-amenities"]
)

api_router.include_router(
    property_images.router,
    prefix="/property-images",
    tags=["property-images"]
)

api_router.include_router(
    favorites.router,
    prefix="/favorites",
    tags=["favorites"]
)

api_router.include_router(
    saved_searches.router,
    prefix="/saved-searches",
    tags=["saved-searches"]
)

api_router.include_router(
    inquiries.router,
    prefix="/inquiries",
    tags=["inquiries"]
)

api_router.include_router(
    reviews.router,
    prefix="/reviews",
    tags=["reviews"]
)


# ROUTER METADATA

# Total routers: 16
# Auth: 2 (auth, admin)
# Core: 4 (users, agencies, agent_profiles, profiles)
# Domain: 4 (locations, properties, property_types, amenities)
# Relations: 6 (property_amenities, property_images, favorites, saved_searches, inquiries, reviews)