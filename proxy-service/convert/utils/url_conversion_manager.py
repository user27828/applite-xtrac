"""
URL Conversion Manager for intelligent URL processing.

This module provides a dedicated layer for handling URL conversions that sits
before the main conversion pipeline. It determines optimal conversion paths
based on service capabilities and handles URL fetching when necessary.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Union, Tuple
from urllib.parse import urlparse
from fastapi import HTTPException, UploadFile

from ..config import ConversionService, CONVERSION_MATRIX, PASSTHROUGH_FORMATS
from .conversion_lookup import get_primary_conversion, get_all_conversions
from .url_fetcher import fetch_url_to_temp_file, detect_content_format, cleanup_temp_file
from .url_helpers import URLFileWrapper

logger = logging.getLogger(__name__)


class ConversionInput(ABC):
    """Abstract base class for different input types."""

    def __init__(self, metadata: Dict[str, Any]):
        self.metadata = metadata

    @abstractmethod
    async def get_for_service(self, service: ConversionService) -> Union[str, UploadFile]:
        """Return input in format expected by service."""
        pass

    @abstractmethod
    async def cleanup(self):
        """Clean up any resources associated with this input."""
        pass


class DirectURLInput(ConversionInput):
    """Input type for services that can handle URLs directly."""

    def __init__(self, url: str, metadata: Dict[str, Any]):
        super().__init__(metadata)
        self.url = url

    async def get_for_service(self, service: ConversionService) -> str:
        """Return URL string for services that support direct URL input."""
        return self.url

    async def cleanup(self):
        """No cleanup needed for direct URL input."""
        pass


class TempFileInput(ConversionInput):
    """Input type for services requiring temp file download."""

    def __init__(self, temp_file_wrapper: URLFileWrapper, metadata: Dict[str, Any]):
        super().__init__(metadata)
        self.temp_file_wrapper = temp_file_wrapper

    async def get_for_service(self, service: ConversionService) -> UploadFile:
        """Return UploadFile wrapper for services requiring file input."""
        # Create a new wrapper instance for each service to avoid cleanup conflicts
        from .url_helpers import URLFileWrapper
        return URLFileWrapper(
            self.temp_file_wrapper.file_path,
            self.temp_file_wrapper.filename,
            self.temp_file_wrapper.content_type
        )

    async def cleanup(self):
        """Clean up temp file resources."""
        if self.temp_file_wrapper:
            await self.temp_file_wrapper.close()
            # Clean up temp file on disk
            if hasattr(self.temp_file_wrapper, 'file_path'):
                cleanup_temp_file(self.temp_file_wrapper.file_path)


class URLConversionManager:
    """Manager for intelligent URL-based conversions."""

    def __init__(self):
        self.service_capabilities = self._load_service_capabilities()

    def _load_service_capabilities(self) -> Dict[str, Dict]:
        """Load service capabilities from configuration."""
        return {
            "gotenberg": {
                "supports_direct_url": True,
                "supported_url_formats": ["html", "pdf", "auto"],
                "supported_input_formats": ["html"],  # Gotenberg can handle HTML URLs directly
                "endpoint_mapping": {
                    "html": "forms/chromium/convert/url",
                    "pdf": "forms/chromium/convert/url"
                }
            },
            "unstructured-io": {
                "supports_direct_url": False,
                "requires_temp_file": True,
                "supported_input_formats": ["html", "pdf", "docx", "xlsx", "pptx", "txt", "md", "json"]
            },
            "libreoffice": {
                "supports_direct_url": False,
                "requires_temp_file": True,
                "supported_input_formats": ["doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp", "rtf", "txt", "html", "pdf"]
            },
            "pandoc": {
                "supports_direct_url": False,
                "requires_temp_file": True,
                "supported_input_formats": ["docx", "html", "md", "txt", "tex", "latex", "rtf", "odt"]
            },
            "local": {
                "supports_direct_url": True,
                "direct_url_formats": ["html"],
                "supported_input_formats": ["html", "txt", "md", "tex"]
            }
        }

    def _detect_url_content_format(self, url: str) -> str:
        """Detect the content format from URL."""
        parsed = urlparse(url)
        path = parsed.path.lower()

        # Check file extension
        if path.endswith(('.html', '.htm')):
            return 'html'
        elif path.endswith('.pdf'):
            return 'pdf'
        elif path.endswith(('.doc', '.docx')):
            return 'docx'
        elif path.endswith(('.xls', '.xlsx')):
            return 'xlsx'
        elif path.endswith(('.ppt', '.pptx')):
            return 'pptx'
        elif path.endswith('.txt'):
            return 'txt'
        elif path.endswith('.md'):
            return 'md'
        elif path.endswith(('.tex', '.latex')):
            return 'tex'
        elif path.endswith('.json'):
            return 'json'
        else:
            # Default to HTML for web content
            return 'html'

    def _find_best_service(self, input_format: str, output_format: str) -> ConversionService:
        """Find the best service for a given conversion."""
        # Get all available services for this conversion
        available_services = get_all_conversions(input_format, output_format)

        if not available_services:
            raise HTTPException(
                status_code=400,
                detail=f"No conversion available for {input_format} to {output_format}"
            )

        # Return the first (highest priority) service
        service, _ = available_services[0]
        return service

    def can_service_handle_url_directly(self, service: str, target_format: str) -> bool:
        """Check if service can handle URL directly for target format."""
        caps = self.service_capabilities.get(service, {})
        return caps.get("supports_direct_url", False) and \
               target_format in caps.get("supported_url_formats", [])

    def can_service_handle_format(self, service: str, input_format: str) -> bool:
        """Check if service can handle a specific input format."""
        caps = self.service_capabilities.get(service, {})
        return input_format in caps.get("supported_input_formats", [])

    async def _fetch_to_temp_file(self, url: str) -> Tuple[URLFileWrapper, Dict[str, Any]]:
        """Fetch URL to temp file and return wrapper."""
        try:
            temp_path, fetch_result = await fetch_url_to_temp_file(url)

            # Detect actual format from content
            detected_format = detect_content_format(
                fetch_result['content'],
                fetch_result.get('content_type', ''),
                url
            )

            # Create file wrapper
            filename = temp_path.name if hasattr(temp_path, 'name') else f"url_content.{detected_format}"
            content_type = fetch_result.get('content_type', f'application/{detected_format}')

            file_wrapper = URLFileWrapper(str(temp_path), filename, content_type)

            metadata = {
                'temp_file_path': str(temp_path),
                'detected_format': detected_format,
                'content_type': content_type,
                'final_url': fetch_result.get('final_url'),
                'status_code': fetch_result.get('status'),
                'fetch_headers': fetch_result.get('headers', {})
            }

            return file_wrapper, metadata

        except Exception as e:
            logger.error(f"Failed to fetch URL {url}: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch URL content: {str(e)}"
            )

    def get_optimal_conversion_path(self, url: str, target_format: str) -> Dict[str, Any]:
        """Determine optimal conversion path for URL."""
        # Detect content format from URL
        detected_format = self._detect_url_content_format(url)

        # Find best service for this conversion
        primary_service = self._find_best_service(detected_format, target_format)

        # Determine if direct URL or temp file needed
        use_direct_url = self.can_service_handle_url_directly(
            primary_service.value, target_format
        )

        # Check if service can handle the detected format
        can_handle_format = self.can_service_handle_format(
            primary_service.value, detected_format
        )

        return {
            "detected_format": detected_format,
            "primary_service": primary_service,
            "use_direct_url": use_direct_url,
            "can_handle_format": can_handle_format,
            "requires_temp_file": not use_direct_url,
            "conversion_path": "direct_url" if use_direct_url else "temp_file_conversion"
        }

    async def process_url_conversion(self, url: str, target_format: str) -> ConversionInput:
        """Main entry point - returns ConversionInput ready for conversion pipeline."""
        # Validate URL format
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
            if parsed.scheme not in ['http', 'https']:
                raise ValueError("Only HTTP and HTTPS URLs are supported")
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid URL: {str(e)}"
            )

        # Detect content format from URL
        detected_format = self._detect_url_content_format(url)

        # Check if this is a passthrough conversion (same format and format is allowed for passthrough)
        if detected_format == target_format and detected_format in PASSTHROUGH_FORMATS:
            # For passthrough conversions, we can return the URL directly
            # or fetch to temp file depending on service capabilities
            metadata = {
                'source': 'url',
                'original_url': url,
                'detected_format': detected_format,
                'conversion_path': 'direct_url',
                'passthrough_conversion': True
            }
            return DirectURLInput(url, metadata)
        elif detected_format == target_format and detected_format not in PASSTHROUGH_FORMATS:
            # Same format but not allowed for passthrough
            raise HTTPException(
                status_code=400,
                detail=f"Passthrough not allowed for format {detected_format}. Use a different output format."
            )

        # Get optimal conversion path for different formats
        path_info = self.get_optimal_conversion_path(url, target_format)

        if path_info["use_direct_url"]:
            # Return URL wrapper that services can handle directly
            metadata = {
                'source': 'url',
                'original_url': url,
                'detected_format': path_info["detected_format"],
                'conversion_path': 'direct_url'
            }
            return DirectURLInput(url, metadata)
        else:
            # Fetch to temp file and return file wrapper
            temp_file_wrapper, fetch_metadata = await self._fetch_to_temp_file(url)

            # Combine metadata
            metadata = {
                'source': 'url',
                'original_url': url,
                'detected_format': path_info["detected_format"],
                'conversion_path': 'temp_file',
                **fetch_metadata
            }

            return TempFileInput(temp_file_wrapper, metadata)
