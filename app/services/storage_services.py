# app/services/storage_services.py
"""
Supabase Storage service - handles file uploads/deletes with security
Production-ready with proper error handling, logging, and image optimization
"""

from io import BytesIO
from typing import Tuple
from PIL import Image
import logging

from app.core.config import settings
from app.utils.supabase_client import get_supabase_client


logger = logging.getLogger(__name__)


# Image size constants (configured per use case)
PROFILE_IMAGE_SIZE: Tuple[int, int] = (512, 512)
AGENCY_LOGO_SIZE: Tuple[int, int] = (512, 512)
PROPERTY_IMAGE_SIZE: Tuple[int, int] = (1200, 800)

# Allowed storage buckets (security whitelist)
ALLOWED_BUCKETS = {"property-images", "profile-images", "agency-logos"}

# Supported image formats
SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP"}


def resize_image(file_data: bytes, size: Tuple[int, int] = (512, 512)) -> bytes:
    """
    Resize image to a fixed size while maintaining aspect ratio.
    
    Args:
        file_data: Original image bytes
        size: Target size as (width, height) tuple
        
    Returns:
        Resized image bytes optimized for storage
        
    Raises:
        ValueError: If image format is unsupported or file is corrupted
    """
    try:
        with Image.open(BytesIO(file_data)) as img:
            # Convert RGBA to RGB for JPEG compatibility
            if img.mode == 'RGBA' and img.format == 'JPEG':
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[3])
                img = rgb_img
            
            # Resize maintaining aspect ratio
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Determine output format
            output_format = img.format
            if not output_format or output_format not in SUPPORTED_FORMATS:
                output_format = "JPEG"  # Safe default for photos
            
            # Save optimized image
            buf = BytesIO()
            img.save(buf, format=output_format, optimize=True, quality=85)
            buf.seek(0)
            return buf.read()
            
    except Exception as e:
        logger.error(
            "Image resize failed",
            extra={"error_type": type(e).__name__},
            exc_info=True
        )
        raise ValueError("Invalid image file. Please upload a valid JPEG, PNG, or WEBP image.")


async def upload_file(bucket_name: str, file_path: str, file_data: bytes) -> str:
    """
    Upload a file to Supabase Storage.
    
    Args:
        bucket_name: Target bucket
        file_path: Path within bucket
        file_data: File bytes
    
    Returns:
        Public URL of uploaded file
    
    Raises:
        ValueError: Generic error for client (no internal details)
    """
    # Validate bucket name (security)
    if bucket_name not in ALLOWED_BUCKETS:
        logger.warning(
            "Attempted upload to unauthorized bucket",
            extra={"bucket_attempt": bucket_name}
        )
        raise ValueError("Invalid storage bucket.")
    
    client = get_supabase_client()

    try:
        response = client.storage.from_(bucket_name).upload(
            file_path, 
            file_data, 
            {"upsert": True}
        )

        if response.get("error"):
            # Log internal error but return generic message
            logger.error(
                "Storage upload failed",
                extra={
                    "bucket": bucket_name,
                    "path": file_path,
                    "error": response.get("error")
                },
                exc_info=True
            )
            raise ValueError("Failed to upload file. Please try again.")

        # Get public URL
        public_url = client.storage.from_(bucket_name).get_public_url(file_path)
        
        logger.info(
            "File uploaded successfully",
            extra={
                "bucket": bucket_name,
                "path": file_path
            }
        )
        
        return public_url

    except ValueError:
        # Re-raise domain errors
        raise
    except Exception as e:
        # Log full error internally
        logger.error(
            "Unexpected storage error",
            extra={
                "bucket": bucket_name,
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        # Return generic message to client
        raise ValueError("Storage service unavailable. Please try again later.")


async def upload_profile_image(user_id: int, file_data: bytes, file_name: str) -> str:
    """
    Upload a profile image with resizing.
    
    Args:
        user_id: User ID for organizing files
        file_data: Image file bytes
        file_name: Original filename
    
    Returns:
        Public URL of uploaded image
    """
    safe_filename = ''.join(c for c in file_name if c.isalnum() or c in '._-')
    bucket_name = "profile-images"
    file_path = f"{user_id}/{safe_filename}"
    resized_image = resize_image(file_data, size=PROFILE_IMAGE_SIZE)
    return await upload_file(bucket_name, file_path, resized_image)


async def upload_agency_logo(agency_id: int, file_data: bytes, file_name: str) -> str:
    """
    Upload an agency logo with resizing.
    
    Args:
        agency_id: Agency ID for organizing files
        file_data: Image file bytes
        file_name: Original filename
    
    Returns:
        Public URL of uploaded image
    """
    safe_filename = ''.join(c for c in file_name if c.isalnum() or c in '._-')
    bucket_name = "agency-logos"
    file_path = f"{agency_id}/{safe_filename}"
    resized_image = resize_image(file_data, size=AGENCY_LOGO_SIZE)
    return await upload_file(bucket_name, file_path, resized_image)


async def upload_property_image(property_id: int, contents: bytes, filename: str) -> str:
    """
    Upload a property image to Supabase Storage.
    Property images are stored at higher resolution for quality.
    
    Args:
        property_id: Property ID for organizing files
        contents: Image file bytes
        filename: Original filename
    
    Returns:
        Public URL of uploaded image
    """
    safe_filename = ''.join(c for c in filename if c.isalnum() or c in '._-')
    bucket_name = "property-images"
    file_path = f"{property_id}/{safe_filename}"
    
    # Resize to optimal property image size (larger than profiles/logos)
    resized_image = resize_image(contents, size=PROPERTY_IMAGE_SIZE)
    
    return await upload_file(bucket_name, file_path, resized_image)


async def delete_file(bucket_name: str, file_path: str) -> bool:
    """
    Delete a file from Supabase Storage.
    
    Args:
        bucket_name: Target bucket
        file_path: Path within bucket
    
    Returns:
        True if successful
    
    Raises:
        ValueError: Generic error for client (no internal details)
    """
    # Validate bucket name (security)
    if bucket_name not in ALLOWED_BUCKETS:
        logger.warning(
            "Attempted delete from unauthorized bucket",
            extra={"bucket_attempt": bucket_name}
        )
        raise ValueError("Invalid storage bucket.")
    
    client = get_supabase_client()

    try:
        response = client.storage.from_(bucket_name).remove([file_path])

        if response.get("error"):
            # Log internal error but return generic message
            logger.error(
                "Storage delete failed",
                extra={
                    "bucket": bucket_name,
                    "path": file_path,
                    "error": response.get("error")
                },
                exc_info=True
            )
            raise ValueError("Failed to delete file. Please try again.")

        logger.info(
            "File deleted successfully",
            extra={
                "bucket": bucket_name,
                "path": file_path
            }
        )
        
        return True

    except ValueError:
        # Re-raise domain errors
        raise
    except Exception as e:
        # Log full error internally
        logger.error(
            "Unexpected delete error",
            extra={
                "bucket": bucket_name,
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        # Return generic message to client
        raise ValueError("Storage service unavailable. Please try again later.")


async def delete_property_image(image_url: str) -> None:
    """
    Delete a property image from Supabase Storage.
    
    Args:
        image_url: Full public URL of the image to delete
    
    Extracts bucket and path from URL and deletes the file.
    Safe to call even if file doesn't exist (idempotent).
    """
    try:
        # Parse URL to extract bucket and path
        # Example: https://xxx.supabase.co/storage/v1/object/public/property-images/123/image.jpg
        
        if '/storage/v1/object/public/' not in image_url:
            # Invalid URL format - log but don't expose details to client
            logger.warning(
                "Invalid storage URL format",
                extra={"url_length": len(image_url)}
            )
            raise ValueError("Invalid image URL format.")
        
        url_parts = image_url.split('/storage/v1/object/public/')
        full_path = url_parts[1]  # e.g., "property-images/123/image.jpg"
        
        path_segments = full_path.split('/')
        if len(path_segments) < 2:
            logger.warning("Malformed storage path")
            raise ValueError("Invalid image path.")
        
        bucket_name = path_segments[0]  # "property-images"
        file_path = '/'.join(path_segments[1:])  # "123/image.jpg"
        
        # Validate bucket name (security - prevent path traversal)
        if bucket_name not in ALLOWED_BUCKETS:
            logger.warning(
                "Attempted access to unauthorized bucket",
                extra={"bucket_attempt": bucket_name}
            )
            raise ValueError("Unauthorized bucket access.")
        
        await delete_file(bucket_name, file_path)
        
    except ValueError:
        # Re-raise domain errors (already safe messages)
        raise
    except Exception as e:
        # Log full error internally, return safe message
        logger.warning(
            "Failed to delete property image",
            extra={"error_type": type(e).__name__},
            exc_info=True
        )
        # Don't fail the operation - image might already be deleted
        # This makes delete idempotent (safe to retry)
        pass


# Export public functions
__all__ = [
    "upload_profile_image",
    "upload_agency_logo",
    "upload_property_image",
    "delete_property_image",
    "resize_image"
]