"""
Phase G.7 production smoke runner.

This intentionally creates disposable production smoke records through the API.
It uses the production DB read-only for backend JWT bootstrapping because the
canonical production accounts do not store plaintext passwords in the repo.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.security import generate_access_token


BASE_URL = "https://realtornet-production.up.railway.app"
API_URL = f"{BASE_URL}/api/v1"


@dataclass(frozen=True)
class SmokeUser:
    user_id: int
    email: str
    role: str
    agency_id: int | None
    supabase_id: str


def _fetch_user(email: str) -> SmokeUser:
    engine = create_engine(settings.DATABASE_URI)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                select user_id, email, user_role, agency_id, supabase_id
                from users
                where email = :email and deleted_at is null
                """
            ),
            {"email": email},
        ).mappings().one()

    return SmokeUser(
        user_id=int(row["user_id"]),
        email=str(row["email"]),
        role=str(row["user_role"]),
        agency_id=row["agency_id"],
        supabase_id=str(row["supabase_id"]),
    )


def _token_for(user: SmokeUser) -> str:
    return generate_access_token(
        supabase_id=UUID(user.supabase_id),
        user_id=user.user_id,
        user_role=user.role,
        agency_id=user.agency_id,
    )


def _headers(token: str | None = None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _request(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    token: str | None = None,
    expected: int | tuple[int, ...] = 200,
    **kwargs: Any,
) -> Any:
    response = client.request(method, url, headers=_headers(token), **kwargs)
    expected_codes = (expected,) if isinstance(expected, int) else expected
    if response.status_code not in expected_codes:
        body = response.text[:500]
        raise RuntimeError(f"{method} {url} returned {response.status_code}: {body}")
    if not response.content:
        return None
    return response.json()


def _login(client: httpx.Client, email: str, password: str) -> str:
    payload = {"username": email, "password": password}
    data = _request(
        client,
        "POST",
        f"{API_URL}/auth/login",
        data=payload,
    )
    return str(data["access_token"])


def _register(client: httpx.Client, email: str, password: str, first_name: str) -> dict[str, Any]:
    return _request(
        client,
        "POST",
        f"{API_URL}/auth/register",
        expected=200,
        json={
            "email": email,
            "first_name": first_name,
            "last_name": "Smoke",
            "phone_number": "+2348000000000",
            "user_role": "seeker",
            "password": password,
        },
    )


def main() -> None:
    admin = _fetch_user("apineorbeenga@gmail.com")
    owner = _fetch_user("apineorbeenga@outlook.com")
    agent = _fetch_user("apineorbeenga@yahoo.com")
    seeker = _fetch_user("godwinemagun@gmail.com")

    admin_token = _token_for(admin)
    owner_token = _token_for(owner)
    agent_token = _token_for(agent)
    seeker_token = _token_for(seeker)

    checks: list[str] = []
    stamp = int(time.time())
    password = f"PhaseG7Smoke{stamp}!"
    owner_email = f"phaseg7.owner.{stamp}@smoke.realtornetapp.com"
    invited_agent_email = f"phaseg7.agent.{stamp}@smoke.realtornetapp.com"
    inquiry_seeker_email = f"phaseg7.seeker.{stamp}@smoke.realtornetapp.com"

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        healthz = _request(client, "GET", f"{BASE_URL}/healthz")
        assert healthz["status"] == "ok"
        checks.append("healthz")

        health = _request(client, "GET", f"{BASE_URL}/health")
        assert health["status"] == "healthy"
        checks.append("health")

        agencies = _request(client, "GET", f"{API_URL}/agencies/")
        assert isinstance(agencies, list)
        checks.append("public agencies")

        properties = _request(client, "GET", f"{API_URL}/properties/")
        assert isinstance(properties, list)
        checks.append("public properties")

        featured = _request(client, "GET", f"{API_URL}/properties/featured")
        assert isinstance(featured, list)
        checks.append("featured properties")

        property_types = _request(client, "GET", f"{API_URL}/property-types/")
        assert property_types
        property_type_id = int(property_types[0]["property_type_id"])
        checks.append("property types")

        locations = _request(client, "GET", f"{API_URL}/locations/")
        assert locations
        location_id = int(locations[0]["location_id"])
        checks.append("locations")

        amenities = _request(client, "GET", f"{API_URL}/amenities/")
        assert isinstance(amenities, list)
        checks.append("amenities")

        admin_agencies = _request(
            client,
            "GET",
            f"{API_URL}/admin/agencies/?status=pending",
            token=admin_token,
        )
        assert isinstance(admin_agencies, list)
        checks.append("admin agency queue")

        agency_stats = _request(
            client,
            "GET",
            f"{API_URL}/agencies/{owner.agency_id}/stats",
            token=owner_token,
        )
        assert "property_count" in agency_stats
        checks.append("agency stats")

        my_inquiries = _request(client, "GET", f"{API_URL}/inquiries/", token=seeker_token)
        assert isinstance(my_inquiries, list)
        checks.append("seeker inquiries")

        received = _request(client, "GET", f"{API_URL}/inquiries/received", token=agent_token)
        assert isinstance(received, list)
        checks.append("agent received inquiries")

        _register(client, owner_email, password, "Owner")
        application = _request(
            client,
            "POST",
            f"{API_URL}/agencies/apply/",
            expected=201,
            json={
                "name": f"Phase G7 Smoke Agency {stamp}",
                "description": "Disposable Phase G.7 production smoke agency.",
                "address": "Lekki Phase 1, Lagos",
                "website_url": "https://example.com",
                "owner_email": owner_email,
                "owner_name": "Owner Smoke",
                "owner_phone_number": "+2348000000001",
                "email": f"phaseg7.agency.{stamp}@smoke.realtornetapp.com",
                "phone_number": "+2348000000002",
            },
        )
        agency_id = int(application["agency_id"])

        approved = _request(
            client,
            "PATCH",
            f"{API_URL}/admin/agencies/{agency_id}/approve/",
            token=admin_token,
        )
        assert approved["status"] == "approved"

        owner_login_token = _login(client, owner_email, password)

        _register(client, invited_agent_email, password, "Agent")
        invite = _request(
            client,
            "POST",
            f"{API_URL}/agencies/{agency_id}/invite/",
            token=owner_login_token,
            json={"email": invited_agent_email},
        )
        accepted = _request(
            client,
            "POST",
            f"{API_URL}/agencies/accept-invite/",
            json={"invite_token": invite["invite_token"]},
        )
        assert accepted["status"] == "accepted"

        agent_login_token = _login(client, invited_agent_email, password)
        created_property = _request(
            client,
            "POST",
            f"{API_URL}/properties/",
            token=agent_login_token,
            expected=201,
            json={
                "title": f"Phase G7 Smoke Listing {stamp}",
                "description": "Disposable listing created by the G.7 production smoke journey.",
                "property_type_id": property_type_id,
                "location_id": location_id,
                "price": "75000000",
                "bedrooms": 3,
                "bathrooms": 2,
                "property_size": "120",
                "listing_type": "sale",
                "agency_id": agency_id,
                "latitude": 6.4474,
                "longitude": 3.4746,
                "has_security": True,
            },
        )
        property_id = int(created_property["property_id"])

        verified_property = _request(
            client,
            "PATCH",
            f"{API_URL}/properties/{property_id}/verify",
            token=admin_token,
            json={"moderation_status": "verified", "moderation_reason": "Phase G.7 smoke"},
        )
        assert verified_property["moderation_status"] == "verified"

        agency_inventory = _request(client, "GET", f"{API_URL}/agencies/{agency_id}/properties")
        assert any(int(item["property_id"]) == property_id for item in agency_inventory)

        _register(client, inquiry_seeker_email, password, "Seeker")
        inquiry_token = _login(client, inquiry_seeker_email, password)
        inquiry = _request(
            client,
            "POST",
            f"{API_URL}/inquiries/",
            token=inquiry_token,
            expected=201,
            json={
                "property_id": property_id,
                "message": "Phase G.7 production smoke inquiry.",
            },
        )
        assert int(inquiry["property_id"]) == property_id

        received_after = _request(
            client,
            "GET",
            f"{API_URL}/inquiries/received",
            token=agent_login_token,
        )
        assert any(int(item["inquiry_id"]) == int(inquiry["inquiry_id"]) for item in received_after)

    print(f"12/12 production checks passed: {', '.join(checks)}")
    print(
        "New agency journey passed: "
        f"agency_id={agency_id}, property_id={property_id}, inquiry_id={inquiry['inquiry_id']}"
    )


if __name__ == "__main__":
    main()
