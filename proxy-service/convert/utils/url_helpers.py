"""
Helper utilities for URL-based conversions.

This module provides integration functions to bridge URL fetching
with the existing conversion pipeline.
"""

import os
import logging
from typing import Optional, Dict, Any, Tuple, Set
from pathlib import Path
from urllib.parse import urlparse
from fastapi import UploadFile, HTTPException

from .url_fetcher import (
    fetch_url_to_temp_file,
    cleanup_temp_file,
    TempFileManager,
    detect_content_format,
    should_use_url_fetch,
    URLFetchError
)
from .conversion_lookup import get_supported_conversions

logger = logging.getLogger(__name__)


class URLFileWrapper:
    """Wrapper to make a temporary file look like an UploadFile."""

    def __init__(self, file_path: str, filename: str, content_type: str = None):
        self.file_path = file_path
        self.filename = filename
        self.content_type = content_type or "application/octet-stream"
        self._file = None

    async def read(self, size: int = -1) -> bytes:
        """Read from the temporary file."""
        if self._file is None:
            self._file = open(self.file_path, 'rb')

        if size == -1:
            return self._file.read()
        else:
            return self._file.read(size)

    async def close(self):
        """Close the file handle."""
        if self._file:
            self._file.close()
            self._file = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


async def prepare_url_for_conversion(
    url: str,
    service: str,
    input_format: str = "auto",
    timeout: int = 30
) -> Tuple[Optional[URLFileWrapper], Dict[str, Any]]:
    """
    Prepare a URL for conversion by fetching it if necessary.

    Args:
        url: The URL to process
        service: The target service name
        input_format: Expected input format
        timeout: Fetch timeout in seconds

    Returns:
        Tuple of (file_wrapper, metadata_dict)

    Raises:
        HTTPException: If URL fetching fails
    """
    metadata = {
        'source': 'url',
        'original_url': url,
        'fetch_required': False,
        'temp_file_path': None
    }

    # Check if URL fetching is needed
    if should_use_url_fetch(service, input_format, has_url_input=True):
        try:
            logger.info(f"Fetching URL for {service}: {url}")

            # Fetch URL to temp file
            temp_path, fetch_result = await fetch_url_to_temp_file(url, timeout)

            # Detect actual format from content
            detected_format = detect_content_format(
                fetch_result['content'],
                fetch_result.get('content_type', ''),
                url
            )

            # Create file wrapper
            filename = Path(temp_path).name
            content_type = fetch_result.get('content_type', 'application/octet-stream')

            file_wrapper = URLFileWrapper(temp_path, filename, content_type)

            # Update metadata
            metadata.update({
                'fetch_required': True,
                'temp_file_path': temp_path,
                'detected_format': detected_format,
                'content_type': content_type,
                'final_url': fetch_result.get('final_url'),
                'status_code': fetch_result.get('status'),
                'fetch_headers': fetch_result.get('headers', {})
            })

            logger.info(f"Successfully fetched URL to {temp_path} (format: {detected_format})")
            return file_wrapper, metadata

        except URLFetchError as e:
            logger.error(f"Failed to fetch URL {url}: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch URL content: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error fetching URL {url}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Unexpected error during URL fetch: {str(e)}"
            )

    # No fetching required
    return None, metadata


async def cleanup_conversion_temp_files(metadata: Dict[str, Any]):
    """Clean up temporary files created during conversion."""
    temp_path = metadata.get('temp_file_path')
    if temp_path:
        cleanup_temp_file(temp_path)
        logger.info(f"Cleaned up temporary file: {temp_path}")


def get_url_conversion_info(url: str, service: str, input_format: str) -> Dict[str, Any]:
    """Get information about URL conversion requirements."""
    fetch_required = should_use_url_fetch(service, input_format, has_url_input=True)

    return {
        'url': url,
        'service': service,
        'input_format': input_format,
        'fetch_required': fetch_required,
        'supported': True,  # All combinations are supported with fetching
        'method': 'fetch_and_convert' if fetch_required else 'direct_url'
    }


async def validate_and_prepare_url_conversion(
    url: str,
    service: str,
    input_format: str = "auto",
    timeout: int = 30
) -> Tuple[Optional[URLFileWrapper], Dict[str, Any]]:
    """
    Validate URL and prepare for conversion with comprehensive error handling.

    Args:
        url: The URL to validate and prepare
        service: Target conversion service
        input_format: Expected input format
        timeout: Fetch timeout

    Returns:
        Tuple of (file_wrapper, metadata)

    Raises:
        HTTPException: For validation or preparation errors
    """
    # Basic URL validation
    if not url or not isinstance(url, str):
        raise HTTPException(status_code=400, detail="Invalid URL: URL must be a non-empty string")

    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise HTTPException(status_code=400, detail="Invalid URL format: Missing scheme or domain")
        if parsed.scheme not in ['http', 'https']:
            raise HTTPException(status_code=400, detail="Invalid URL scheme: Only HTTP and HTTPS are supported")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"URL validation failed: {str(e)}")

    # Prepare for conversion
    try:
        file_wrapper, metadata = await prepare_url_for_conversion(
            url, service, input_format, timeout
        )
        return file_wrapper, metadata
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Unexpected error in URL preparation: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal error during URL preparation"
        )


class URLConversionManager:
    """Manager for URL-based conversions with automatic cleanup."""

    def __init__(self):
        self.temp_files = []
        self.metadata = {}

    async def prepare_conversion(
        self,
        url: str,
        service: str,
        input_format: str = "auto",
        timeout: int = 30
    ) -> Tuple[Optional[URLFileWrapper], Dict[str, Any]]:
        """Prepare a URL for conversion and track resources."""
        file_wrapper, metadata = await validate_and_prepare_url_conversion(
            url, service, input_format, timeout
        )

        # Track temp file for cleanup
        if metadata.get('temp_file_path'):
            self.temp_files.append(metadata['temp_file_path'])

        self.metadata = metadata
        return file_wrapper, metadata

    async def cleanup(self):
        """Clean up all temporary resources."""
        for temp_path in self.temp_files:
            cleanup_temp_file(temp_path)
        self.temp_files.clear()
        self.metadata.clear()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()


# Integration helper for existing conversion endpoints
async def handle_url_conversion_request(
    url: str,
    service: str,
    input_format: str = "auto",
    timeout: int = 30
) -> Tuple[Optional[URLFileWrapper], Dict[str, Any]]:
    """
    Handle URL conversion requests with automatic resource management and validation.

    This is the main entry point for integrating URL fetching with
    existing conversion endpoints.

    Args:
        url: The URL to convert
        service: Target service name
        input_format: Input format hint
        timeout: Fetch timeout

    Returns:
        Tuple of (file_wrapper, metadata) for use in conversion

    Raises:
        HTTPException: If URL or content format validation fails
    """
    async with URLConversionManager() as manager:
        # Use the validated version that checks content formats
        file_wrapper, metadata = await validate_url_conversion_request(
            url, service, input_format, timeout
        )

        # Detach from manager to prevent automatic cleanup
        # (caller is responsible for cleanup)
        manager.temp_files.clear()

        return file_wrapper, metadata


def get_supported_input_formats() -> Set[str]:
    """
    Get all supported input formats from the conversion configuration.

    Returns:
        Set of supported input format strings
    """
    supported = get_supported_conversions()
    # Remove 'url' from supported formats as it's not a file format
    return {fmt for fmt in supported.keys() if fmt != 'url'}


def validate_url_content_format(
    url: str,
    detected_format: str,
    content: Optional[bytes] = None,
    content_type: str = ""
) -> str:
    """
    Validate that the URL content format is supported for conversion.

    Args:
        url: The original URL
        detected_format: Format detected from content analysis
        content: Raw content bytes (optional, for additional validation)
        content_type: Content-Type header (optional)

    Returns:
        The validated format string

    Raises:
        HTTPException: If the format is not supported
    """
    supported_formats = get_supported_input_formats()

    # Check if detected format is supported
    if detected_format in supported_formats:
        logger.info(f"URL content format '{detected_format}' is supported")
        return detected_format

    # Special handling for 'auto' format (let it pass through)
    if detected_format == 'auto':
        logger.info("Auto-detected format - allowing to proceed")
        return detected_format

    # Try to map common variations or extensions
    format_mapping = {
        'htm': 'html',  # .htm -> html
        'doc': 'docx',  # .doc -> docx (common assumption)
        'xls': 'xlsx',  # .xls -> xlsx
        'ppt': 'pptx',  # .ppt -> pptx
        'jpeg': 'jpg',  # jpeg -> jpg
        'tiff': 'tif',  # tiff -> tif
    }

    # Check if we can map to a supported format
    mapped_format = format_mapping.get(detected_format.lower())
    if mapped_format and mapped_format in supported_formats:
        logger.info(f"Mapped format '{detected_format}' to supported '{mapped_format}'")
        return mapped_format

    # Additional validation based on content-type
    if content_type:
        content_type_lower = content_type.lower()
        if 'html' in content_type_lower and 'html' in supported_formats:
            logger.info(f"Content-Type '{content_type}' indicates HTML format")
            return 'html'
        elif 'pdf' in content_type_lower and 'pdf' in supported_formats:
            logger.info(f"Content-Type '{content_type}' indicates PDF format")
            return 'pdf'
        elif 'json' in content_type_lower and 'json' in supported_formats:
            logger.info(f"Content-Type '{content_type}' indicates JSON format")
            return 'json'
        elif 'text' in content_type_lower:
            # Default text content to txt if supported
            if 'txt' in supported_formats:
                logger.info(f"Content-Type '{content_type}' indicates text format")
                return 'txt'

    # If we get here, the format is not supported
    error_msg = (
        f"Unsupported content format '{detected_format}' for URL: {url}. "
        f"Supported formats: {', '.join(sorted(supported_formats))}"
    )

    logger.warning(error_msg)
    raise HTTPException(
        status_code=400,
        detail=error_msg
    )


async def validate_url_conversion_request(
    url: str,
    target_service: str,
    input_format: str = "auto",
    timeout: int = 30
) -> Tuple[Optional[URLFileWrapper], Dict[str, Any]]:
    """
    Validate and prepare a URL for conversion with comprehensive format checking.

    Args:
        url: The URL to validate and prepare
        target_service: Target conversion service name
        input_format: Expected input format hint
        timeout: Fetch timeout

    Returns:
        Tuple of (file_wrapper, metadata) if valid

    Raises:
        HTTPException: For validation or preparation errors
    """
    # First validate the URL format
    if not url or not isinstance(url, str):
        raise HTTPException(status_code=400, detail="Invalid URL: URL must be a non-empty string")

    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise HTTPException(status_code=400, detail="Invalid URL format: Missing scheme or domain")
        if parsed.scheme not in ['http', 'https']:
            raise HTTPException(status_code=400, detail="Invalid URL scheme: Only HTTP and HTTPS are supported")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"URL validation failed: {str(e)}")

    # Prepare for conversion
    try:
        file_wrapper, metadata = await prepare_url_for_conversion(
            url, target_service, input_format, timeout
        )

        # If we have fetched content, validate the format
        if file_wrapper and 'detected_format' in metadata:
            detected_format = metadata['detected_format']
            content_type = metadata.get('content_type', '')

            # Validate the detected format
            validated_format = validate_url_content_format(
                url, detected_format, content_type=content_type
            )

            # Update metadata with validated format
            metadata['validated_format'] = validated_format

        return file_wrapper, metadata

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Unexpected error in URL validation: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal error during URL validation"
        )
