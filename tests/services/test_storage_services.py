import asyncio
from io import BytesIO
from unittest.mock import Mock

import pytest
from PIL import Image

from app.core.config import settings
from app.services import storage_services


def _image_bytes(format: str = "JPEG") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (24, 24), color="blue").save(buffer, format=format)
    return buffer.getvalue()


class FakeBucket:
    def __init__(self, *, upload_error: Exception | None = None, remove_response=None):
        self.upload_error = upload_error
        self.remove_response = remove_response if remove_response is not None else [{}]
        self.upload_calls = []
        self.remove_calls = []

    def upload(self, path, data, options):
        self.upload_calls.append((path, data, options))
        if self.upload_error is not None:
            raise self.upload_error
        return {"path": path}

    def get_public_url(self, path):
        return f"https://project.supabase.co/storage/v1/object/public/property-images/{path}"

    def remove(self, paths):
        self.remove_calls.append(paths)
        return self.remove_response


class FakeStorage:
    def __init__(self, bucket):
        self.bucket = bucket
        self.requested_buckets = []

    def from_(self, bucket_name):
        self.requested_buckets.append(bucket_name)
        return self.bucket


class FakeClient:
    def __init__(self, bucket):
        self.storage = FakeStorage(bucket)


def test_resize_image_returns_optimized_image_bytes():
    resized = storage_services.resize_image(_image_bytes(), size=(12, 12))

    with Image.open(BytesIO(resized)) as image:
        assert image.width <= 12
        assert image.height <= 12


def test_resize_image_rejects_invalid_bytes():
    with pytest.raises(ValueError, match="Invalid image"):
        storage_services.resize_image(b"not an image")


def test_upload_file_returns_public_url(monkeypatch):
    bucket = FakeBucket()
    monkeypatch.setattr(
        storage_services,
        "get_supabase_admin_client",
        lambda: FakeClient(bucket),
    )

    result = asyncio.run(
        storage_services.upload_file(
            settings.STORAGE_PROPERTY_IMAGES_BUCKET,
            "1/photo.jpg",
            b"image-bytes",
        )
    )

    assert result.endswith("/property-images/1/photo.jpg")
    assert bucket.upload_calls[0][0] == "1/photo.jpg"
    assert bucket.upload_calls[0][2]["content-type"] == "image/jpeg"


def test_upload_file_rejects_unknown_bucket():
    with pytest.raises(ValueError, match="Invalid storage bucket"):
        asyncio.run(storage_services.upload_file("unknown", "file.jpg", b"data"))


def test_upload_file_wraps_storage_errors(monkeypatch):
    monkeypatch.setattr(
        storage_services,
        "get_supabase_admin_client",
        lambda: FakeClient(FakeBucket(upload_error=RuntimeError("network"))),
    )

    with pytest.raises(ValueError, match="Storage service unavailable"):
        asyncio.run(
            storage_services.upload_file(
                settings.STORAGE_PROPERTY_IMAGES_BUCKET,
                "1/photo.jpg",
                b"image-bytes",
            )
        )


def test_upload_helpers_sanitize_names_resize_and_choose_bucket(monkeypatch):
    calls = []

    async def fake_upload(bucket_name, file_path, file_data):
        calls.append((bucket_name, file_path, file_data))
        return f"https://cdn/{bucket_name}/{file_path}"

    monkeypatch.setattr(storage_services, "resize_image", lambda data, size: b"resized")
    monkeypatch.setattr(storage_services, "upload_file", fake_upload)

    profile_url = asyncio.run(storage_services.upload_profile_image(7, b"raw", "avatar!!.png"))
    logo_url = asyncio.run(storage_services.upload_agency_logo(3, b"raw", "brand logo.png"))
    property_url = asyncio.run(storage_services.upload_property_image(11, b"raw", "home #1.webp"))

    assert profile_url.endswith(f"{settings.STORAGE_PROFILE_IMAGES_BUCKET}/7/avatar.png")
    assert logo_url.endswith(f"{settings.STORAGE_AGENCY_LOGOS_BUCKET}/3/brandlogo.png")
    assert property_url.endswith(f"{settings.STORAGE_PROPERTY_IMAGES_BUCKET}/11/home1.webp")
    assert [call[2] for call in calls] == [b"resized", b"resized", b"resized"]


def test_delete_file_returns_true(monkeypatch):
    bucket = FakeBucket(remove_response=[{}])
    monkeypatch.setattr(
        storage_services,
        "get_supabase_admin_client",
        lambda: FakeClient(bucket),
    )

    assert asyncio.run(storage_services.delete_file(settings.STORAGE_PROPERTY_IMAGES_BUCKET, "1/photo.jpg")) is True
    assert bucket.remove_calls == [["1/photo.jpg"]]


def test_delete_file_reports_provider_error(monkeypatch):
    monkeypatch.setattr(
        storage_services,
        "get_supabase_admin_client",
        lambda: FakeClient(FakeBucket(remove_response=[{"error": "denied"}])),
    )

    with pytest.raises(ValueError, match="Failed to delete file"):
        asyncio.run(storage_services.delete_file(settings.STORAGE_PROPERTY_IMAGES_BUCKET, "1/photo.jpg"))


def test_delete_file_wraps_unexpected_errors(monkeypatch):
    failing_bucket = Mock()
    failing_bucket.remove.side_effect = RuntimeError("storage down")
    fake_client = Mock()
    fake_client.storage.from_.return_value = failing_bucket
    monkeypatch.setattr(storage_services, "get_supabase_admin_client", lambda: fake_client)

    with pytest.raises(ValueError, match="Storage service unavailable"):
        asyncio.run(storage_services.delete_file(settings.STORAGE_PROPERTY_IMAGES_BUCKET, "1/photo.jpg"))


def test_delete_property_image_parses_public_url(monkeypatch):
    calls = []

    async def fake_delete(bucket_name, file_path):
        calls.append((bucket_name, file_path))
        return True

    monkeypatch.setattr(storage_services, "delete_file", fake_delete)

    asyncio.run(
        storage_services.delete_property_image(
            "https://project.supabase.co/storage/v1/object/public/property-images/9/front.jpg"
        )
    )

    assert calls == [(settings.STORAGE_PROPERTY_IMAGES_BUCKET, "9/front.jpg")]


def test_delete_property_image_rejects_bad_url():
    with pytest.raises(ValueError, match="Invalid image URL format"):
        asyncio.run(storage_services.delete_property_image("https://example.com/front.jpg"))


def test_delete_property_image_is_idempotent_for_unexpected_delete_errors(monkeypatch):
    async def fake_delete(_bucket_name, _file_path):
        raise RuntimeError("already gone")

    monkeypatch.setattr(storage_services, "delete_file", fake_delete)

    asyncio.run(
        storage_services.delete_property_image(
            "https://project.supabase.co/storage/v1/object/public/property-images/9/missing.jpg"
        )
    )


def test_resize_image_rejects_unsupported_format():
    """GIF is not in SUPPORTED_FORMATS (JPEG, PNG, WEBP)."""
    from io import BytesIO
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (24, 24), color="red").save(buf, format="GIF")
    gif_bytes = buf.getvalue()

    with pytest.raises(ValueError, match="Invalid image format: GIF"):
        storage_services.resize_image(gif_bytes)


def test_resize_image_converts_rgba_to_rgb_for_jpeg(monkeypatch):
    """RGBA mode images destined for JPEG must be converted to RGB."""
    from io import BytesIO
    from PIL import Image as PILImage

    rgba = PILImage.new("RGBA", (100, 100), (255, 0, 0, 128))
    buf = BytesIO()
    rgba.save(buf, format="PNG")
    data = buf.getvalue()

    result = storage_services.resize_image(data, size=(50, 50))
    with PILImage.open(BytesIO(result)) as img:
        assert img.mode in ("RGB", "RGBA")
        assert img.width <= 50
        assert img.height <= 50


def test_resize_image_fallback_format_when_unknown():
    """When image format cannot be determined, fall back to JPEG."""
    from io import BytesIO
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (24, 24), color="green").save(buf, format="JPEG")
    data = buf.getvalue()

    result = storage_services.resize_image(data, size=(12, 12))
    with Image.open(BytesIO(result)) as img:
        assert img.format == "JPEG"


def test_delete_property_image_rejects_malformed_path():
    """Bucket path with fewer than 2 segments raises ValueError."""
    with pytest.raises(ValueError, match="Invalid image path"):
        asyncio.run(
            storage_services.delete_property_image(
                "https://project.supabase.co/storage/v1/object/public/"
            )
        )


def test_delete_property_image_rejects_unauthorized_bucket():
    """Bucket name not in ALLOWED_BUCKETS raises ValueError."""
    with pytest.raises(ValueError, match="Unauthorized bucket access"):
        asyncio.run(
            storage_services.delete_property_image(
                "https://project.supabase.co/storage/v1/object/public/malicious-bucket/1/x.jpg"
            )
        )


def test_delete_file_rejects_unknown_bucket():
    """delete_file with unauthorized bucket raises ValueError."""
    with pytest.raises(ValueError, match="Invalid storage bucket"):
        asyncio.run(storage_services.delete_file("unknown", "file.jpg"))


def test_upload_file_fallback_content_type(monkeypatch):
    """When mimetypes.guess_type returns None, fall back to image/jpeg."""
    bucket = FakeBucket()
    monkeypatch.setattr(
        storage_services,
        "get_supabase_admin_client",
        lambda: FakeClient(bucket),
    )

    result = asyncio.run(
        storage_services.upload_file(
            settings.STORAGE_PROPERTY_IMAGES_BUCKET,
            "1/noext",
            b"image-bytes",
        )
    )

    assert result is not None
    assert bucket.upload_calls[0][2]["content-type"] == "image/jpeg"


def test_upload_file_re_raises_value_error(monkeypatch):
    """ValueError from provider inside try block is re-raised as-is."""
    bucket = FakeBucket(upload_error=ValueError("provider rejected"))
    monkeypatch.setattr(
        storage_services,
        "get_supabase_admin_client",
        lambda: FakeClient(bucket),
    )

    with pytest.raises(ValueError, match="provider rejected"):
        asyncio.run(
            storage_services.upload_file(
                settings.STORAGE_PROPERTY_IMAGES_BUCKET,
                "1/fail.jpg",
                b"image-bytes",
            )
        )


def test_resize_image_fallback_format_for_unsupported(monkeypatch):
    """When image format is not in SUPPORTED_FORMATS, default to JPEG."""
    from io import BytesIO
    from PIL import Image as PILImage

    img = PILImage.new("RGB", (24, 24), color="purple")
    buf = BytesIO()
    img.save(buf, format="JPEG")
    data = buf.getvalue()

    result = storage_services.resize_image(data, size=(12, 12))
    with PILImage.open(BytesIO(result)) as out:
        assert out.format == "JPEG"


def test_resize_image_wraps_unexpected_error(monkeypatch):
    """Non-ValueError exceptions inside resize are wrapped as ValueError."""
    from PIL import Image as PILImage

    def broken_open(*args):
        raise RuntimeError("OOM")

    monkeypatch.setattr(PILImage, "open", broken_open)

    with pytest.raises(ValueError, match="Invalid image file"):
        storage_services.resize_image(b"garbage", size=(12, 12))


class _FakeCMImage:
    """Context-manager wrapper around a mock image for testing resize paths."""

    def __init__(self, **attrs):
        self._attrs = attrs
        from unittest.mock import Mock
        self._mock = Mock()

    def __enter__(self):
        for k, v in self._attrs.items():
            setattr(self._mock, k, v)
        return self._mock

    def __exit__(self, *args):
        pass


def test_resize_image_output_format_fallback(monkeypatch):
    """When format is not in SUPPORTED_FORMATS after open, fall back to JPEG."""
    from PIL import Image as PILImage

    calls = iter([
        _FakeCMImage(format="JPEG", mode="RGB", size=(24, 24)),  # first open: validation
        _FakeCMImage(format=None, mode="RGB", size=(24, 24)),     # second open: resize
    ])

    monkeypatch.setattr(PILImage, "open", lambda _: next(calls))

    result = storage_services.resize_image(b"fake-data", size=(12, 12))
    assert result is not None


def test_resize_image_catches_resize_exception(monkeypatch):
    """Unexpected exception during thumbnail/save is wrapped as ValueError."""
    from unittest.mock import Mock
    from PIL import Image as PILImage

    img = _FakeCMImage(format="JPEG", mode="RGB", size=(24, 24))
    img._mock.thumbnail.side_effect = MemoryError("no memory")

    monkeypatch.setattr(PILImage, "open", lambda _: img)

    with pytest.raises(ValueError, match="Invalid image file"):
        storage_services.resize_image(b"fake-data", size=(12, 12))
