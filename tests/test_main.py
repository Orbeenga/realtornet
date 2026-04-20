from app import main
from fastapi.testclient import TestClient


def test_run_storage_bucket_bootstrap_marks_ready_on_success(monkeypatch):
    class _Result:
        def __init__(self, name: str, action: str):
            self.name = name
            self.action = action
            self.public = True
            self.allowed_mime_types = ("image/jpeg",)

    monkeypatch.setattr(main.settings, "ENV", "production")
    monkeypatch.setattr(
        main,
        "ensure_required_storage_buckets",
        lambda: [_Result("property-images", "verified")],
    )

    payload = main._run_storage_bucket_bootstrap()

    assert payload["ready"] is True
    assert payload["error"] is None
    assert payload["results"][0]["name"] == "property-images"


def test_run_storage_bucket_bootstrap_fails_open_on_error(monkeypatch):
    monkeypatch.setattr(main.settings, "ENV", "production")

    def _raise() -> list[object]:
        raise RuntimeError("service role key missing")

    monkeypatch.setattr(main, "ensure_required_storage_buckets", _raise)

    payload = main._run_storage_bucket_bootstrap()

    assert payload["ready"] is False
    assert payload["results"] == []
    assert payload["error"] == "service role key missing"


def test_healthz_returns_200_when_storage_bootstrap_failed():
    """
    Railway only cares that the healthcheck responds with HTTP 200.

    The body can report degraded dependencies, but the process must stay alive
    and answer `/healthz` even when startup storage checks failed.
    """
    client = TestClient(main.app)
    main.app.state.storage_bucket_bootstrap = {
        "ready": False,
        "results": [],
        "error": "service role key missing",
    }

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["storage"]["ready"] is False
