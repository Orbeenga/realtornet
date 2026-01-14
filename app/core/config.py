# app/core/config.py
"""
RealtorNet Configuration Module
Phase 2 Aligned: Psycopg 3, production-ready settings, 1:1 .env match
"""

import urllib.parse
from typing import List, Union, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """RealtorNet application configuration with canonical alignment."""
    
    # Project metadata
    PROJECT_NAME: str = "RealtorNet"
    API_V1_STR: str = "/api/v1"
    
    # Supabase configuration
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str = ""  # Optional for admin operations
    
    # Database configuration (matches .env structure)
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: str = "6543"
    DATABASE_URL: str = ""  # Optional: direct connection string override
    
    # Test database
    TEST_POSTGRES_DB: str = "test_db"
    
    # Security configuration
    SECRET_KEY: str = ""  # Must be 64+ chars (256-bit) in production
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ALGORITHM: str = "HS256"
    PASSWORD_MIN_LENGTH: int = 12
    MAX_LOGIN_ATTEMPTS: int = 5
    
    # CORS configuration - accepts string or list from .env
    BACKEND_CORS_ORIGINS: List[str] = []
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        """Convert comma-separated string or JSON array from .env into Python list."""
        if isinstance(v, str):
            # Handle JSON array format: ["url1","url2"]
            if v.startswith("["):
                import json
                return json.loads(v)
            # Handle comma-separated format: url1,url2
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        raise ValueError(f"Invalid CORS origins format: {v}")
    
    # Environment
    ENV: str = "development"
    DEBUG: bool = False
    TESTING: bool = False
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None
    
    # Redis configuration (matches .env structure)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_CELERY_BROKER: str = "redis://localhost:6379/1"
    REDIS_CELERY_BACKEND: str = "redis://localhost:6379/2"
    
    # Storage bucket configuration
    STORAGE_PROFILE_IMAGES_BUCKET: str = "profile-images"
    STORAGE_AGENCY_LOGOS_BUCKET: str = "agency-logos"
    STORAGE_PROPERTY_IMAGES_BUCKET: str = "property-images"

    # Caching
    CACHE_BACKEND: str = "memory"
    CACHE_TTL: int = 300
    
    # Database connection pool settings
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10  # Matches SQLAlchemy's max_overflow parameter
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    
    # Email configuration (matches .env structure)
    SMTP_HOST: str = "smtp.mailgun.org"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "RealtorNet <noreply@yourdomain.com>"
    
    # Mailgun configuration
    MAILGUN_API_KEY: str = ""
    MAILGUN_DOMAIN: str = ""
    MAIL_FROM: str = "RealtorNet <no-reply@your-domain.com>"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )
    
    @property
    def is_dev(self) -> bool:
        """Check if running in development mode."""
        return self.ENV == "development"
    
    @property
    def DATABASE_URI(self) -> str:
        """
        Primary database connection URI using psycopg (v3).
        Priority: DATABASE_URL > constructed from components
        """
        if self.DATABASE_URL:
            # Ensure psycopg driver (not psycopg2)
            if "psycopg2" in self.DATABASE_URL:
                return self.DATABASE_URL.replace("psycopg2", "psycopg")
            return self.DATABASE_URL
        
        # Construct from components
        password = urllib.parse.quote_plus(self.POSTGRES_PASSWORD)
        ssl = "disable" if self.POSTGRES_SERVER == "localhost" else "require"
        
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{password}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            f"?sslmode={ssl}"
        )
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Alias for SQLAlchemy/Alembic compatibility."""
        return self.DATABASE_URI
    
    @property
    def TEST_DATABASE_URI(self) -> str:
        """Test database connection string."""
        if self.DATABASE_URL:
            # Replace database name in existing URL
            base_parts = self.DATABASE_URL.split('?')
            base_url = base_parts[0]
            
            if "psycopg2" in base_url:
                base_url = base_url.replace("psycopg2", "psycopg")
            
            if '/' in base_url:
                base_url = base_url.rsplit('/', 1)[0] + '/' + self.TEST_POSTGRES_DB
            
            query_params = base_parts[1] if len(base_parts) > 1 else "sslmode=require"
            return f"{base_url}?{query_params}"
        
        # Construct test URL from components
        password = urllib.parse.quote_plus(self.POSTGRES_PASSWORD)
        ssl = "disable" if self.POSTGRES_SERVER == "localhost" else "require"
        
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{password}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.TEST_POSTGRES_DB}"
            f"?sslmode={ssl}"
        )
    
    def validate_cors_origins(self) -> List[str]:
        """Validate and sanitize CORS origins."""
        if "*" in self.BACKEND_CORS_ORIGINS:
            return ["*"]
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS if origin.strip()]
    
    def validate_secret_key(self) -> None:
        """
        Validate SECRET_KEY meets security requirements.
        Minimum 64 chars (256-bit) for production.
        """
        if not self.SECRET_KEY:
            if self.ENV == "production":
                raise ValueError(
                    "SECRET_KEY is required in production. "
                    "Generate with: python -c 'import secrets; print(secrets.token_hex(32))'"
                )
            print("⚠️  WARNING: SECRET_KEY not set. Generate with: secrets.token_hex(32)")
            return
        
        if len(self.SECRET_KEY) < 64:
            if self.ENV == "production":
                raise ValueError(
                    f"SECRET_KEY must be at least 64 characters (256-bit) in production. "
                    f"Current length: {len(self.SECRET_KEY)}"
                )
            print(f"⚠️  WARNING: SECRET_KEY is only {len(self.SECRET_KEY)} chars (recommended: 64+)")


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings retrieval for performance.
    Validates security requirements on startup.
    """
    settings_instance = Settings()
    settings_instance.validate_secret_key()
    return settings_instance


settings = get_settings()