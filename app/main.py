# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.exceptions import ErrorHandler, ApplicationException
from app.core.logging import logger
from app.core.config import settings
from app.api.api import api_router
from app.middleware.request_middleware import RedisRateLimitMiddleware
from app.api.endpoints import analytics

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    logger.info("RealtorNet application starting up")
    
    if settings.is_dev:
        logger.warning(
            "Running in development mode — ensure DB is migrated via Alembic. "
            "Never use Base.metadata.create_all() for schema management."
        )
        
    yield
    logger.info("RealtorNet application shutting down")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
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

# Include Analytics Services
app.include_router(analytics.router, prefix="/api")


@app.get("/")
def health_check():
    """Root health check endpoint."""
    logger.info("Health check endpoint accessed")
    return {
        "status": "healthy",
        "message": "Welcome to RealtorNet!",
        "version": "2.0"
    }


@app.get("/example-error")
def trigger_example_error():
    """Endpoint to demonstrate custom exception handling."""
    raise ApplicationException(
        message="Example error demonstration",
        status_code=400,
        details={"reason": "Demonstration purposes"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)