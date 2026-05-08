from app.models.locations import Location


def test_location_repr_and_invalid_geom_fallback() -> None:
    location = Location(location_id=1, state="Lagos", city="Ikeja")

    assert repr(location) == "<Location(location_id=1, state=Lagos, city=Ikeja)>"

    location.__dict__["geom"] = object()
    assert location.latitude is None
    assert location.longitude is None
