# app/main.py
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.api import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import ApplicationException, ErrorHandler
from app.core.logging import logger
from app.middleware.request_middleware import RedisRateLimitMiddleware
from app.services.storage_bucket_bootstrap import ensure_required_storage_buckets


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    logger.info("RealtorNet application starting up")

    if settings.SENTRY_DSN:
        try:
            import sentry_sdk
        except ImportError:
            logger.warning(
                "SENTRY_DSN is set but sentry-sdk is not installed; skipping Sentry initialization"
            )
        else:
            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                environment=settings.ENV,
                release="realtornet-backend@0.5.2",
                traces_sample_rate=0.1,
            )
            logger.info("Sentry instrumentation initialized")

    if settings.is_dev:
        logger.warning(
            "Running in development mode - ensure DB is migrated via Alembic. "
            "Never use Base.metadata.create_all() for schema management."
        )

    if settings.ENV != "test":
        bucket_results = ensure_required_storage_buckets()
        app.state.storage_bucket_bootstrap = {
            "ready": True,
            "results": [result.__dict__ for result in bucket_results],
        }
    else:
        app.state.storage_bucket_bootstrap = {"ready": True, "results": []}

    yield
    logger.info("RealtorNet application shutting down")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.validate_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
app.add_middleware(RedisRateLimitMiddleware)

# Add global exception handler
app.add_exception_handler(Exception, ErrorHandler.global_exception_handler)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def health_check():
    """Root health check endpoint."""
    logger.info("Health check endpoint accessed")
    return {
        "status": "healthy",
        "message": "Welcome to RealtorNet!",
        "version": "2.0",
    }


@app.get("/healthz")
def health_simple():
    return {
        "status": "ok",
        "storage": getattr(app.state, "storage_bucket_bootstrap", {"ready": False}),
    }


@app.get("/health")
def health_check_full():  # pragma: no cover
    """Readiness probe - checks DB connectivity. Used by deployment health checks."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "version": "2.0",
        }
    except Exception as e:
        from fastapi import Response
        import json

        return Response(
            content=json.dumps(
                {
                    "status": "unhealthy",
                    "database": "unreachable",
                    "detail": str(e),
                }
            ),
            status_code=503,
            media_type="application/json",
        )


@app.get("/example-error")
def trigger_example_error():
    """Endpoint to demonstrate custom exception handling."""
    raise ApplicationException(
        message="Example error demonstration",
        status_code=400,
        details={"reason": "Demonstration purposes"},
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
