from types import SimpleNamespace

from app.services import location_resolution_service as service
from app.services.location_resolution_service import NominatimLocationResolver, ResolvedLocation


def test_nominatim_search_parses_and_caches(monkeypatch):
    resolver = NominatimLocationResolver()
    calls = []

    def fake_fetch(query: str, *, limit: int):
        calls.append((query, limit))
        return [
            {
                "lat": "6.4281",
                "lon": "3.4219",
                "address": {
                    "state": "Lagos",
                    "city": "Lagos",
                    "suburb": "Victoria Island",
                },
            }
        ]

    monkeypatch.setattr(resolver, "_fetch", fake_fetch)

    first = resolver.search("Victoria Island Lagos", limit=1)
    second = resolver.search("Victoria Island Lagos", limit=1)

    assert calls == [("Victoria Island Lagos", 1)]
    assert first == second
    assert first[0] == ResolvedLocation(
        state="lagos",
        city="lagos",
        neighborhood="victoria island",
        latitude=6.4281,
        longitude=3.4219,
    )


def test_nominatim_search_returns_empty_on_fetch_failure(monkeypatch):
    resolver = NominatimLocationResolver()

    def fake_fetch(query: str, *, limit: int):
        raise RuntimeError("network down")

    monkeypatch.setattr(resolver, "_fetch", fake_fetch)

    assert resolver.search("Nowhere", limit=1) == []


def test_nominatim_search_returns_empty_for_blank_query():
    resolver = NominatimLocationResolver()

    assert resolver.search("   ") == []


def test_resolve_one_returns_first_result(monkeypatch):
    resolver = NominatimLocationResolver()
    resolved = ResolvedLocation("lagos", "lagos", None, None, None)
    monkeypatch.setattr(resolver, "search", lambda query, limit: [resolved])

    assert resolver.resolve_one("lagos") is resolved


def test_fetch_calls_nominatim_with_policy_headers(monkeypatch):
    resolver = NominatimLocationResolver()
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"address": {}}, "ignore me"]

    def fake_get(url, *, params, headers, timeout):
        captured.update(
            {
                "url": url,
                "params": params,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return FakeResponse()

    monkeypatch.setattr(service.time, "monotonic", lambda: 10.0)
    monkeypatch.setattr(service.httpx, "get", fake_get)

    assert resolver._fetch("lekki", limit=3) == [{"address": {}}]
    assert captured["url"].endswith("/search")
    assert captured["params"] == {
        "q": "lekki",
        "format": "json",
        "limit": 3,
        "addressdetails": 1,
    }
    assert captured["headers"]["User-Agent"]


def test_fetch_returns_empty_for_non_list_payload(monkeypatch):
    resolver = NominatimLocationResolver()

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"unexpected": "shape"}

    monkeypatch.setattr(service.time, "monotonic", lambda: 10.0)
    monkeypatch.setattr(service.httpx, "get", lambda *args, **kwargs: FakeResponse())

    assert resolver._fetch("lekki", limit=1) == []


def test_parse_result_falls_back_when_address_is_sparse():
    resolver = NominatimLocationResolver()

    parsed = resolver._parse_result(
        {"lat": None, "lon": "bad", "address": {"state": "Lagos"}},
        fallback_query="Lekki Lagos",
    )

    assert parsed == ResolvedLocation(
        state="lagos",
        city="lagos",
        neighborhood=None,
        latitude=None,
        longitude=None,
    )


def test_parse_result_handles_missing_address_and_state():
    resolver = NominatimLocationResolver()

    parsed = resolver._parse_result(
        {"lat": "6.5", "lon": "3.4", "address": "bad"},
        fallback_query="Lekki Lagos",
    )

    assert parsed == ResolvedLocation(
        state="lekki lagos",
        city="lekki lagos",
        neighborhood=None,
        latitude=6.5,
        longitude=3.4,
    )


def test_resolve_location_name_to_record_uses_get_or_create(monkeypatch):
    expected = SimpleNamespace(location_id=123)
    resolved = ResolvedLocation(
        state="lagos",
        city="lagos",
        neighborhood="lekki",
        latitude=6.4698,
        longitude=3.5852,
    )

    monkeypatch.setattr(service.location_resolver, "resolve_one", lambda query: resolved)

    def fake_get_or_create(db, **kwargs):
        assert kwargs == {
            "state": "lagos",
            "city": "lagos",
            "neighborhood": "lekki",
            "latitude": 6.4698,
            "longitude": 3.5852,
        }
        return expected

    monkeypatch.setattr(service.location_crud, "get_or_create", fake_get_or_create)

    assert service.resolve_location_name_to_record(object(), location_name="Lekki Lagos") is expected


def test_resolve_location_name_to_record_returns_none_without_match(monkeypatch):
    monkeypatch.setattr(service.location_resolver, "resolve_one", lambda query: None)

    assert service.resolve_location_name_to_record(object(), location_name="No Match") is None


def test_search_locations_via_nominatim_deduplicates_records(monkeypatch):
    record = SimpleNamespace(location_id=5)
    monkeypatch.setattr(
        service.location_resolver,
        "search",
        lambda query, limit: [
            ResolvedLocation("lagos", "lagos", "lekki", 6.4, 3.5),
            ResolvedLocation("lagos", "lagos", "lekki", 6.4, 3.5),
        ],
    )
    monkeypatch.setattr(service.location_crud, "get_or_create", lambda db, **kwargs: record)

    assert service.search_locations_via_nominatim(object(), query="lekki") == [record]
