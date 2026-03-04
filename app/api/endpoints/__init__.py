# app/api/endpoints/__init__.py

from . import auth
from . import admin
from . import users
from . import agencies
from . import agent_profiles
from . import profiles
from . import locations
from . import properties
from . import property_types
from . import amenities
from . import property_amenities
from . import property_images
from . import favorites
from . import saved_searches
from . import inquiries
from . import reviews

__all__ = [
    "auth", "admin", "users", "agencies", "agent_profiles", "profiles",
    "locations", "properties", "property_types", "amenities",
    "property_amenities", "property_images", "favorites",
    "saved_searches", "inquiries", "reviews"
]
