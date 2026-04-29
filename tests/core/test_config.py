from app.core.config import Settings
from app.middleware.request_middleware import _redact_redis_url


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_ANON_KEY": "anon",
        "POSTGRES_SERVER": "localhost",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "postgres",
        "POSTGRES_DB": "realtornet",
        "SECRET_KEY": "x" * 64,
    }
    values.update(overrides)
    return Settings(**values)


def test_redis_url_populates_celery_urls_with_stable_db_paths():
    settings = _settings(REDIS_URL="redis://default:secret@redis.railway.internal:6379/0")

    assert settings.REDIS_CELERY_BROKER == (
        "redis://default:secret@redis.railway.internal:6379/1"
    )
    assert settings.REDIS_CELERY_BACKEND == (
        "redis://default:secret@redis.railway.internal:6379/2"
    )


def test_railway_redis_parts_populate_celery_urls_when_redis_url_is_absent():
    settings = _settings(
        REDISHOST="redis.railway.internal",
        REDISPORT=6379,
        REDISUSER="default",
        REDISPASSWORD="pa ss/word",
    )

    assert settings.REDIS_CELERY_BROKER == (
        "redis://default:pa%20ss%2Fword@redis.railway.internal:6379/1"
    )
    assert settings.REDIS_CELERY_BACKEND == (
        "redis://default:pa%20ss%2Fword@redis.railway.internal:6379/2"
    )


def test_explicit_celery_redis_urls_are_preserved():
    settings = _settings(
        REDIS_URL="redis://default:secret@redis.railway.internal:6379",
        REDIS_CELERY_BROKER="redis://custom-broker:6379/9",
        REDIS_CELERY_BACKEND="redis://custom-backend:6379/8",
    )

    assert settings.REDIS_CELERY_BROKER == "redis://custom-broker:6379/9"
    assert settings.REDIS_CELERY_BACKEND == "redis://custom-backend:6379/8"


def test_redis_url_redaction_removes_credentials():
    assert _redact_redis_url("redis://default:secret@redis.railway.internal:6379/1") == (
        "redis://***@redis.railway.internal:6379/1"
    )
