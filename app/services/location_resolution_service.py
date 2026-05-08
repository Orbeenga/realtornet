# app/services/location_resolution_service.py
"""Server-side Nominatim location resolution for property workflows."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, cast

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud.locations import location as location_crud
from app.models.locations import Location


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedLocation:
    state: str
    city: str
    neighborhood: str | None
    latitude: float | None
    longitude: float | None


class NominatimLocationResolver:
    """Resolve free-text locations through Nominatim with process-local throttling."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, list[ResolvedLocation]]] = {}
        self._lock = threading.Lock()
        self._last_request_at = 0.0

    def resolve_one(self, query: str) -> ResolvedLocation | None:
        results = self.search(query, limit=1)
        return results[0] if results else None

    def search(self, query: str, *, limit: int = 5) -> list[ResolvedLocation]:
        normalized_query = query.strip()
        if not normalized_query:
            return []

        cache_key = f"{normalized_query.lower()}:{limit}"
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if cached and now - cached[0] < settings.NOMINATIM_CACHE_TTL_SECONDS:
            return cached[1]

        try:
            payload = self._fetch(normalized_query, limit=limit)
        except Exception:
            logger.warning(
                "Nominatim location lookup failed",
                extra={"query": normalized_query},
                exc_info=True,
            )
            return []

        results = [
            resolved
            for item in payload
            if (resolved := self._parse_result(item, fallback_query=normalized_query)) is not None
        ]
        self._cache[cache_key] = (time.monotonic(), results)
        return results

    def _fetch(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            wait_seconds = settings.NOMINATIM_REQUEST_INTERVAL_SECONDS - elapsed
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            self._last_request_at = time.monotonic()

        response = httpx.get(
            f"{settings.NOMINATIM_BASE_URL.rstrip('/')}/search",
            params={
                "q": query,
                "format": "json",
                "limit": limit,
                "addressdetails": 1,
            },
            headers={"User-Agent": settings.NOMINATIM_USER_AGENT},
            timeout=settings.NOMINATIM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def _parse_result(self, item: dict[str, Any], *, fallback_query: str) -> ResolvedLocation | None:
        address = item.get("address")
        if not isinstance(address, dict):
            address = {}

        state = self._first_text(address, "state", "region", "state_district")
        city = self._first_text(
            address,
            "city",
            "town",
            "village",
            "municipality",
            "county",
            "state_district",
        )
        neighborhood = self._first_text(address, "neighbourhood", "suburb", "quarter", "city_district")

        if not state:
            state = city or fallback_query
        if not city:
            city = state

        latitude = self._to_float(item.get("lat"))
        longitude = self._to_float(item.get("lon"))

        return ResolvedLocation(
            state=state.strip().lower(),
            city=city.strip().lower(),
            neighborhood=neighborhood.strip().lower() if neighborhood else None,
            latitude=latitude,
            longitude=longitude,
        )

    @staticmethod
    def _first_text(source: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


location_resolver = NominatimLocationResolver()


def resolve_location_name_to_record(db: Session, *, location_name: str) -> Location | None:
    resolved = location_resolver.resolve_one(location_name)
    if resolved is None:
        logger.warning(
            "Nominatim returned no location result; storing free-text location only",
            extra={"location_name": location_name},
        )
        return None

    return location_crud.get_or_create(
        db,
        state=resolved.state,
        city=resolved.city,
        neighborhood=resolved.neighborhood,
        latitude=resolved.latitude,
        longitude=resolved.longitude,
    )


def search_locations_via_nominatim(db: Session, *, query: str, limit: int = 5) -> list[Location]:
    records: list[Location] = []
    seen_ids: set[int] = set()
    for resolved in location_resolver.search(query, limit=limit):
        record = location_crud.get_or_create(
            db,
            state=resolved.state,
            city=resolved.city,
            neighborhood=resolved.neighborhood,
            latitude=resolved.latitude,
            longitude=resolved.longitude,
        )
        location_id = cast(int, record.location_id)
        if location_id not in seen_ids:
            records.append(record)
            seen_ids.add(location_id)
    return records
