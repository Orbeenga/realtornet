#/app/core/exceptions.py
import uuid
from typing import Optional, Any, Dict
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

class ErrorDetails(BaseModel):
    """
    Standardized error response model for consistent error reporting
    """
    error_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status_code: int
    message: str
    details: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "error_id": "123e4567-e89b-12d3-a456-426614174000",
                "status_code": 400,
                "message": "Invalid request parameters",
                "details": {
                    "field": "user_email",
                    "reason": "Invalid email format"
                }
            }
        }

class ApplicationException(Exception):
    """
    Base custom exception for application-specific errors
    """
    def __init__(self, 
                 message: str, 
                 status_code: int = 500, 
                 details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class ErrorHandler:
    """
    Centralized error handling and logging mechanism
    """
    @staticmethod
    async def global_exception_handler(request: Request, exc: Exception):
        """
        Global exception handler for FastAPI
        Provides consistent error response across application
        """
        from app.core.logging import logger  # Local import to avoid circular dependencies

        # Different handling for known exception types
        if isinstance(exc, ApplicationException):
            error = ErrorDetails(
                status_code=exc.status_code,
                message=exc.message,
                details=exc.details
            )
            logger.error(f"Application Exception: {error.model_dump_json()}")
            return JSONResponse(
                status_code=exc.status_code,
                content=error.model_dump()
            )
        
        elif isinstance(exc, HTTPException):
            error = ErrorDetails(
                status_code=exc.status_code,
                message=exc.detail
            )
            logger.warning(f"HTTP Exception: {error.model_dump_json()}")
            return JSONResponse(
                status_code=exc.status_code,
                content=error.model_dump()
            )
        
        # Generic exception handling
        error = ErrorDetails(
            status_code=500,
            message="Internal Server Error",
            details={
                "exception_type": type(exc).__name__,
                "exception_message": str(exc)
            }
        )
        logger.error(f"Unhandled Exception: {error.model_dump_json()}", exc_info=True)
        
        return JSONResponse(
            status_code=500,
            content=error.model_dump()
        )

# Pre-defined common application exceptions
class ValidationException(ApplicationException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=422, details=details)

class AuthenticationException(ApplicationException):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)

class AuthorizationException(ApplicationException):
    def __init__(self, message: str = "Authorization denied"):
        super().__init__(message, status_code=403)

class ResourceNotFoundException(ApplicationException):
    def __init__(self, resource: str, identifier: Any):
        message = f"{resource} with identifier {identifier} not found"
        super().__init__(message, status_code=404)

# Example of how to use in an endpoint
def example_endpoint():
    try:
        # Some business logic
        if not valid_condition:
            raise ValidationException(
                "Invalid input", 
                details={"field": "user_email", "reason": "Invalid format"}
            )
    except ApplicationException as e:
        # Automatically handled by global exception handler
        raise