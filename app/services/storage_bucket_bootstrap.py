"""
Supabase Storage bucket provisioning and validation.

Ensures the application's required public image buckets exist with the expected
visibility and MIME restrictions before traffic is served.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from app.core.config import settings
from app.utils.supabase_client import get_supabase_admin_client


logger = logging.getLogger(__name__)

IMAGE_BUCKET_ALLOWED_MIME_TYPES = ("image/jpeg", "image/png", "image/webp")


@dataclass(frozen=True)
class StorageBucketSpec:
    name: str
    public: bool = True
    allowed_mime_types: tuple[str, ...] = IMAGE_BUCKET_ALLOWED_MIME_TYPES

    def to_update_options(self) -> dict[str, Any]:
        return {
            "public": self.public,
            "allowed_mime_types": list(self.allowed_mime_types),
        }


@dataclass(frozen=True)
class StorageBucketProvisionResult:
    name: str
    action: str
    public: bool
    allowed_mime_types: tuple[str, ...]


def get_required_storage_bucket_specs() -> tuple[StorageBucketSpec, ...]:
    """Return the canonical bucket definitions required by RealtorNet."""
    return (
        StorageBucketSpec(name=settings.STORAGE_PROPERTY_IMAGES_BUCKET),
        StorageBucketSpec(name=settings.STORAGE_PROFILE_IMAGES_BUCKET),
        StorageBucketSpec(name=settings.STORAGE_AGENCY_LOGOS_BUCKET),
    )


def _normalize_mime_types(values: Any) -> tuple[str, ...]:
    if not values:
        return ()
    return tuple(sorted(str(value) for value in values))


def _bucket_matches_spec(existing_bucket: Any, spec: StorageBucketSpec) -> bool:
    existing_public = bool(getattr(existing_bucket, "public", False))
    existing_mime_types = _normalize_mime_types(
        getattr(existing_bucket, "allowed_mime_types", None)
    )
    return (
        existing_public == spec.public
        and existing_mime_types == _normalize_mime_types(spec.allowed_mime_types)
    )


def ensure_required_storage_buckets() -> list[StorageBucketProvisionResult]:
    """
    Validate and provision required Supabase Storage buckets.

    Creates missing buckets and updates existing buckets that drifted away from
    the expected public-image configuration.
    """
    client = get_supabase_admin_client()
    existing_buckets = {bucket.id: bucket for bucket in client.storage.list_buckets()}
    results: list[StorageBucketProvisionResult] = []

    for spec in get_required_storage_bucket_specs():
        existing_bucket = existing_buckets.get(spec.name)

        if existing_bucket is None:
            client.storage.create_bucket(spec.name, options=spec.to_update_options())
            action = "created"
        elif not _bucket_matches_spec(existing_bucket, spec):
            client.storage.update_bucket(spec.name, spec.to_update_options())
            action = "updated"
        else:
            action = "verified"

        logger.info(
            "Supabase storage bucket ready",
            extra={
                "bucket": spec.name,
                "action": action,
                "public": spec.public,
                "allowed_mime_types": list(spec.allowed_mime_types),
            },
        )
        results.append(
            StorageBucketProvisionResult(
                name=spec.name,
                action=action,
                public=spec.public,
                allowed_mime_types=spec.allowed_mime_types,
            )
        )

    return results


__all__ = [
    "IMAGE_BUCKET_ALLOWED_MIME_TYPES",
    "StorageBucketProvisionResult",
    "StorageBucketSpec",
    "ensure_required_storage_buckets",
    "get_required_storage_bucket_specs",
]
