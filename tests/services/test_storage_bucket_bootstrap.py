from types import SimpleNamespace

from app.services.storage_bucket_bootstrap import (
    IMAGE_BUCKET_ALLOWED_MIME_TYPES,
    ensure_required_storage_buckets,
)


class FakeStorageClient:
    def __init__(self, buckets):
        self._buckets = list(buckets)
        self.created = []
        self.updated = []

    def list_buckets(self):
        return list(self._buckets)

    def create_bucket(self, bucket_id, options=None, name=None):
        self.created.append((bucket_id, options, name))
        self._buckets.append(
            SimpleNamespace(
                id=bucket_id,
                public=bool((options or {}).get("public", False)),
                allowed_mime_types=(options or {}).get("allowed_mime_types"),
            )
        )
        return {"id": bucket_id}

    def update_bucket(self, bucket_id, options):
        self.updated.append((bucket_id, options))
        for bucket in self._buckets:
            if bucket.id == bucket_id:
                bucket.public = bool(options.get("public", False))
                bucket.allowed_mime_types = options.get("allowed_mime_types")
                break
        return {"id": bucket_id}


class FakeSupabaseClient:
    def __init__(self, buckets):
        self.storage = FakeStorageClient(buckets)


def test_bootstrap_creates_missing_buckets(monkeypatch):
    fake_client = FakeSupabaseClient(buckets=[])
    monkeypatch.setattr(
        "app.services.storage_bucket_bootstrap.get_supabase_admin_client",
        lambda: fake_client,
    )

    results = ensure_required_storage_buckets()

    assert [result.action for result in results] == ["created", "created", "created"]
    assert [bucket_id for bucket_id, _, _ in fake_client.storage.created] == [
        "property-images",
        "profile-images",
        "agency-logos",
    ]
    for _, options, _ in fake_client.storage.created:
        assert options == {
            "public": True,
            "allowed_mime_types": list(IMAGE_BUCKET_ALLOWED_MIME_TYPES),
        }


def test_bootstrap_updates_drifted_bucket(monkeypatch):
    fake_client = FakeSupabaseClient(
        buckets=[
            SimpleNamespace(
                id="property-images",
                public=False,
                allowed_mime_types=["image/jpeg"],
            ),
            SimpleNamespace(
                id="profile-images",
                public=True,
                allowed_mime_types=list(IMAGE_BUCKET_ALLOWED_MIME_TYPES),
            ),
            SimpleNamespace(
                id="agency-logos",
                public=True,
                allowed_mime_types=list(IMAGE_BUCKET_ALLOWED_MIME_TYPES),
            ),
        ]
    )
    monkeypatch.setattr(
        "app.services.storage_bucket_bootstrap.get_supabase_admin_client",
        lambda: fake_client,
    )

    results = ensure_required_storage_buckets()

    assert [result.action for result in results] == ["updated", "verified", "verified"]
    assert fake_client.storage.updated == [
        (
            "property-images",
            {
                "public": True,
                "allowed_mime_types": list(IMAGE_BUCKET_ALLOWED_MIME_TYPES),
            },
        )
    ]


def test_bootstrap_verifies_already_correct_buckets(monkeypatch):
    fake_client = FakeSupabaseClient(
        buckets=[
            SimpleNamespace(
                id="property-images",
                public=True,
                allowed_mime_types=["image/png", "image/jpeg", "image/webp"],
            ),
            SimpleNamespace(
                id="profile-images",
                public=True,
                allowed_mime_types=["image/jpeg", "image/png", "image/webp"],
            ),
            SimpleNamespace(
                id="agency-logos",
                public=True,
                allowed_mime_types=["image/webp", "image/png", "image/jpeg"],
            ),
        ]
    )
    monkeypatch.setattr(
        "app.services.storage_bucket_bootstrap.get_supabase_admin_client",
        lambda: fake_client,
    )

    results = ensure_required_storage_buckets()

    assert [result.action for result in results] == ["verified", "verified", "verified"]
    assert fake_client.storage.created == []
    assert fake_client.storage.updated == []
