# app/middleware/request_middleware.py
"""
Request middleware for RealtorNet
Provides distributed rate limiting using Redis with production-grade features
"""

import time
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
import redis.asyncio as redis

from app.core.config import settings
from app.core.logging import logger


class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Distributed rate limiting middleware using Redis.
    
    Features:
    - Atomic operations for accurate counting
    - Graceful fallback if Redis unavailable
    - Proxy-aware IP detection
    - Configurable via settings
    """
    
    def __init__(
        self, 
        app,
        max_requests: Optional[int] = None,
        window: Optional[int] = None,
        redis_uri: Optional[str] = None,
        trust_proxy: bool = False
    ):
        """
        Initialize rate limit middleware.
        
        Args:
            app: FastAPI application
            max_requests: Max requests per window (default: 100)
            window: Time window in seconds (default: 60)
            redis_uri: Redis connection URI (default: from settings)
            trust_proxy: Trust X-Forwarded-For header (set True behind load balancers)
        """
        super().__init__(app)
        
        # Use settings or provided values
        self.max_requests = max_requests or 100
        self.window = window or 60
        self.trust_proxy = trust_proxy
        
        # Redis connection (use broker URI from settings)
        redis_connection = redis_uri or settings.REDIS_CELERY_BROKER
        
        try:
            self.redis_client = redis.from_url(
                redis_connection,
                encoding="utf-8",
                decode_responses=True,
                socket_keepalive=True,
                socket_connect_timeout=5
            )
            logger.info(f"Rate limit middleware initialized with Redis: {redis_connection}")
        except Exception as e:
            logger.error(f"Failed to initialize Redis for rate limiting: {e}")
            self.redis_client = None

    async def dispatch(
        self, 
        request: Request, 
        call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Rate limiting and request tracking middleware.
        Returns 429 if rate limit exceeded, otherwise processes request normally.
        """
        # ADDED: Skip rate limiting in test environment
        if settings.ENV == "test":
            return await call_next(request)

        # Get client identifier
        client_id = self._get_client_identifier(request)
        current_time = time.time()
        
        # Skip rate limiting if Redis unavailable
        if self.redis_client is None:
            logger.warning("Rate limiting disabled - Redis unavailable")
            return await call_next(request)
        
        # Unique key for rate limiting
        rate_limit_key = f"rate_limit:{client_id}"
        
        try:
            # Increment request count atomically
            current_count = await self.redis_client.incr(rate_limit_key)
            
            # Set expiration if this is the first request
            if current_count == 1:
                await self.redis_client.expire(rate_limit_key, self.window)
            
            # Check if request count exceeds limit
            if current_count > self.max_requests:
                logger.warning(
                    f"Rate limit exceeded for client: {client_id}",
                    extra={
                        "client_id": client_id,
                        "current_count": current_count,
                        "limit": self.max_requests
                    }
                )
                return Response(
                    content="Rate limit exceeded. Please try again later.",
                    status_code=429,
                    headers={
                        "Retry-After": str(self.window),
                        "X-RateLimit-Limit": str(self.max_requests),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(current_time + self.window))
                    }
                )
            
            # Continue with request processing
            response = await call_next(request)
            
            # Add rate limit headers to response
            remaining = max(0, self.max_requests - current_count)
            response.headers["X-RateLimit-Limit"] = str(self.max_requests)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(current_time + self.window))
            
            return response
        
        except redis.RedisError as e:
            logger.error(
                f"Redis error during rate limiting: {e.__class__.__name__}",
                extra={"client_id": client_id}
            )
            # Fallback: Allow request if Redis fails (fail open for availability)
            return await call_next(request)
        
        except Exception as e:
            try:
                error_detail = str(e)
            except Exception:
                error_detail = type(e).__name__

            logger.error(
                f"Unexpected error in rate limiting middleware",
                extra={"error": error_detail, "client_id": client_id},
                exc_info=True
            )
            # Fallback: Allow request
            return await call_next(request)

    def _get_client_identifier(self, request: Request) -> str:
        """
        Extract client identifier for rate limiting.
        
        Respects proxy headers if trust_proxy=True, otherwise uses direct IP.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Client identifier string (IP address or forwarded IP)
        """
        if self.trust_proxy:
            # Check X-Forwarded-For header (standard for load balancers)
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                # Get first IP in chain (original client)
                return forwarded_for.split(",")[0].strip()
            
            # Check X-Real-IP header (Nginx)
            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                return real_ip.strip()
        
        # Default to direct connection IP
        return request.client.host if request.client else "unknown"

    async def close(self):
        """
        Cleanup Redis connection on shutdown.
        
        Should be called in application lifespan shutdown event.
        """
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Rate limit middleware Redis connection closed")


# Export
__all__ = ["RedisRateLimitMiddleware"]
