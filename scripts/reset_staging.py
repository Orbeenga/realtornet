"""
One-time and repeatable staging reset utility.
Purges all transactional data, preserves real accounts, reseeds reference data.
Run before pytest when staging has accumulated test artifacts.
"""
import os
import sys
from sqlalchemy import create_engine, text

STAGING_ID = "avkhpachzsbgmbnkfnhu"
PRESERVED_EMAILS = {
    'apineorbeenga@gmail.com',
    'apineorbeenga@outlook.com',
    'apineorbeenga@yahoo.com',
    'apineterngu19@gmail.com',
    'godwinemagun@gmail.com'
}


def get_engine():
    url = os.environ.get("DATABASE_URL", "")
    if STAGING_ID not in url:
        print(f"ERROR: DATABASE_URL does not point at staging ({STAGING_ID}). Aborting.")
        sys.exit(1)
    return create_engine(url)


def purge(conn):
    append_only = [
        "agent_membership_audit",
        "listing_events",
        "listing_instructions",
        "notifications",
        "inquiry_replies",
    ]
    for table in append_only:
        conn.execute(text(f"TRUNCATE {table} CASCADE"))
        print(f"  truncated {table}")

    tables = [
        "favorites",
        "reviews",
        "inquiries",
        "saved_searches",
        "property_amenities",
        "property_images",
        "properties",
        "agency_invitations",
        "agency_membership_review_requests",
        "review_requests",
        "agency_join_requests",
        "agency_agent_memberships",
        "agent_profiles",
        "profiles",
        "locations",
        "amenities",
        "property_types",
        "agencies",
    ]
    for table in tables:
        conn.execute(text(f"DELETE FROM {table}"))
        print(f"  cleared {table}")

    placeholders = ", ".join(f"'{e}'" for e in PRESERVED_EMAILS)
    conn.execute(text(f"DELETE FROM users WHERE email NOT IN ({placeholders})"))
    print(f"  cleared users (preserved {len(PRESERVED_EMAILS)} accounts)")


def reseed(conn):
    property_types = [
        "Apartment", "House", "Bungalow", "Duplex", "Condo", "Townhouse",
        "Land", "Commercial", "Office", "Warehouse", "Shop", "Semi-detached"
    ]
    for name in property_types:
        conn.execute(text(
            "INSERT INTO property_types (name) VALUES (:n) ON CONFLICT DO NOTHING"
        ), {"n": name})
    print(f"  seeded {len(property_types)} property types")

    amenities = [
        "Parking", "Swimming Pool", "Gym", "Security", "Generator",
        "Air Conditioning", "Furnished", "Water Supply", "Internet", "Garden",
        "Balcony", "Elevator", "CCTV", "Boys Quarters", "Solar Power"
    ]
    for name in amenities:
        conn.execute(text(
            "INSERT INTO amenities (name) VALUES (:n) ON CONFLICT DO NOTHING"
        ), {"n": name})
    print(f"  seeded {len(amenities)} amenities")

    nigerian_states = ["Lagos", "Abuja", "Kano", "Rivers", "Oyo"]
    for state in nigerian_states:
        conn.execute(text(
            "INSERT INTO locations (state, city, neighborhood) VALUES (:st, :st, 'Central') ON CONFLICT DO NOTHING"
        ), {"st": state})
    print(f"  seeded {len(nigerian_states)} Nigerian states")


def validate(conn):
    pt_count = conn.execute(text("SELECT COUNT(*) FROM property_types")).scalar()
    am_count = conn.execute(text("SELECT COUNT(*) FROM amenities")).scalar()
    user_count = conn.execute(text("SELECT COUNT(*) FROM users WHERE deleted_at IS NULL")).scalar()
    loc_count = conn.execute(text("SELECT COUNT(*) FROM locations")).scalar()
    assert pt_count == 12, f"Expected 12 property types, got {pt_count}"
    assert am_count == 15, f"Expected 15 amenities, got {am_count}"
    assert user_count == len(PRESERVED_EMAILS), f"Expected {len(PRESERVED_EMAILS)} users, got {user_count}"
    assert loc_count == 5, f"Expected 5 locations, got {loc_count}"
    print(f"  validated: {pt_count} types, {am_count} amenities, {user_count} users, {loc_count} locations")


if __name__ == "__main__":
    engine = get_engine()
    print("Resetting staging...")
    with engine.begin() as conn:
        purge(conn)
        reseed(conn)
        validate(conn)
    print("Done. Staging is clean.")
