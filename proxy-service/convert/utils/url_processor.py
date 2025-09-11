"""
Consolidated URL Processing Module

This module provides a unified interface for URL-based document processing,
consolidating functionality from url_fetcher.py, url_helpers.py, and url_conversion_manager.py
with clear separation of concerns.

Architecture:
- URLProcessor: Main orchestrator and public API
- URLFetcher: Handles HTTP requests and content retrieval
- ContentAnalyzer: Handles format detection and content analysis
- FileManager: Handles temp file operations and UploadFile wrapping
- ServiceRouter: Handles service capability decisions and routing logic
"""

import os
import asyncio
import logging
import hashlib
import tempfile
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Union, Tuple
from pathlib import Path
from urllib.parse import urlparse, unquote
import mimetypes

# Try to import magic for content-based detection
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    magic = None
    MAGIC_AVAILABLE = False

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from fastapi import HTTPException, UploadFile

from ..config import ConversionService, CONVERSION_MATRIX, PASSTHROUGH_FORMATS
from .conversion_lookup import get_primary_conversion, get_all_conversions
from .temp_file_manager import get_temp_manager
from .mime_detector import get_mime_type as get_unified_mime_type, get_format_from_mime_type
from .logging_config import get_logger

logger = get_logger()

# Configuration constants
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_SIZE = 50 * 1024 * 1024  # 50MB
TEMP_DIR = "/tmp/applite-xtrac"


class URLProcessingError(Exception):
    """Custom exception for URL processing errors."""
    pass


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

    def __init__(self, file_wrapper, metadata: Dict[str, Any]):
        super().__init__(metadata)
        self.file_wrapper = file_wrapper

    async def get_for_service(self, service: ConversionService) -> UploadFile:
        """Return UploadFile wrapper for services requiring file input."""
        # Create a new wrapper instance for each service to avoid cleanup conflicts
        return URLFileWrapper(
            self.file_wrapper.file_path,
            self.file_wrapper.filename,
            self.file_wrapper.content_type
        )

    async def cleanup(self):
        """Clean up temp file resources."""
        if self.file_wrapper:
            await self.file_wrapper.close()


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

    async def seek(self, position: int) -> None:
        """Seek to a position in the file."""
        if self._file is None:
            self._file = open(self.file_path, 'rb')
        self._file.seek(position)

    async def close(self):
        """Close the file handle."""
        if self._file:
            self._file.close()
            self._file = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class ContentAnalyzer:
    """Handles content format detection and analysis."""

    @staticmethod
    def detect_format_from_url(url: str) -> str:
        """Detect content format from URL path."""
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

    @staticmethod
    def detect_format_from_content(content: bytes, content_type: str = '', url: str = '') -> str:
        """
        Detect the actual content format from content, content-type, and URL.

        Priority order:
        1. Content-based detection (using python-magic if available)
        2. Content-type header analysis
        3. URL-based detection as fallback
        4. Basic content analysis for common formats
        """
        try:
            # Method 1: Content-based detection using python-magic
            if MAGIC_AVAILABLE and content:
                try:
                    detected_mime = magic.from_buffer(content, mime=True)
                    if detected_mime:
                        detected_format = get_format_from_mime_type(detected_mime)
                        if detected_format:
                            logger.debug(f"Content-based detection: {detected_format} (MIME: {detected_mime})")
                            return detected_format
                except Exception as e:
                    logger.debug(f"Magic content detection failed: {e}")

            # Method 2: Content-type header analysis
            if content_type:
                detected_format = get_format_from_mime_type(content_type)
                if detected_format:
                    logger.debug(f"Content-type detection: {detected_format} (MIME: {content_type})")
                    return detected_format

            # Method 3: URL-based detection as fallback
            if url:
                url_content_type = get_unified_mime_type(filename=url)
                if url_content_type:
                    detected_format = get_format_from_mime_type(url_content_type)
                    if detected_format:
                        logger.debug(f"URL-based detection: {detected_format} (MIME: {url_content_type})")
                        return detected_format

            # Method 4: Basic content analysis for common formats
            if content:
                # Check for PDF signature
                if content.startswith(b'%PDF-'):
                    logger.debug("Content analysis: pdf (PDF signature detected)")
                    return 'pdf'

                # Check for common HTML patterns
                content_str = content[:1024].decode('utf-8', errors='ignore').lower()
                if '<html' in content_str or '<!doctype html' in content_str:
                    logger.debug("Content analysis: html (HTML tags detected)")
                    return 'html'

                # Check for JSON
                try:
                    import json
                    json.loads(content_str.strip())
                    logger.debug("Content analysis: json (valid JSON detected)")
                    return 'json'
                except (json.JSONDecodeError, ValueError):
                    pass

            # Default fallback
            logger.debug("Using default format: html")
            return 'html'

        except Exception as e:
            logger.warning(f"Content format detection failed: {e}")
            return 'html'  # Safe default

    @staticmethod
    def get_content_type_from_url(url: str) -> str:
        """Guess content type from URL."""
        parsed = urlparse(url)
        path = unquote(parsed.path)

        # Try to guess from file extension using unified detector
        content_type = get_unified_mime_type(filename=path)

        if content_type:
            return content_type

        # Default to HTML for URLs without extensions
        return 'text/html'


class URLFetcher:
    """Handles HTTP requests and content retrieval."""

    @staticmethod
    def create_session_with_retries() -> requests.Session:
        """Create a requests session with retry configuration."""
        session = requests.Session()

        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    @staticmethod
    async def fetch_content(url: str, timeout: int = DEFAULT_TIMEOUT, user_agent: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch URL content using requests.

        Args:
            url: The URL to fetch
            timeout: Timeout in seconds
            user_agent: Custom User-Agent string

        Returns:
            Dict containing content, content_type, final_url, status, headers

        Raises:
            URLProcessingError: If fetching fails
        """
        try:
            session = URLFetcher.create_session_with_retries()

            # Use provided user agent or default
            request_user_agent = user_agent or 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

            response = session.get(
                url,
                timeout=timeout,
                headers={
                    'User-Agent': request_user_agent,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                },
                stream=True
            )

            response.raise_for_status()

            # Read content with size limit
            content = b''
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > DEFAULT_MAX_SIZE:
                    raise URLProcessingError(f"Content size exceeds maximum limit of {DEFAULT_MAX_SIZE} bytes")

            return {
                'content': content,
                'content_type': response.headers.get('Content-Type', ''),
                'final_url': response.url,
                'status': response.status_code,
                'headers': dict(response.headers)
            }

        except requests.RequestException as e:
            logger.error(f"Requests fetch failed for {url}: {e}")
            raise URLProcessingError(f"Failed to fetch URL: {str(e)}")


class FileManager:
    """Handles temp file operations and UploadFile wrapping."""

    @staticmethod
    def generate_temp_filename(url: str, content_type: str = None) -> str:
        """Generate a temporary filename for the fetched content."""
        parsed = urlparse(url)
        path = unquote(parsed.path)

        # Extract filename from URL path
        if path and path != '/':
            filename = Path(path).name
            if filename and '.' in filename:
                return filename

        # Generate filename based on URL hash if no extension found
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

        # Guess extension from content type
        if content_type:
            if 'html' in content_type:
                ext = 'html'
            elif 'pdf' in content_type:
                ext = 'pdf'
            elif 'text' in content_type:
                ext = 'txt'
            elif 'json' in content_type:
                ext = 'json'
            else:
                ext = 'bin'
        else:
            ext = 'html'  # Default

        return f"url_content_{url_hash}.{ext}"

    @staticmethod
    async def save_to_temp_file(content: bytes, filename: str) -> str:
        """
        Save content to a temporary file using the centralized manager.

        Args:
            content: The content to save
            filename: The filename to use

        Returns:
            The path to the saved file
        """
        manager = get_temp_manager("url_processor")
        temp_file = manager.create_temp_file(content=content, filename=filename)
        return temp_file.path

    @staticmethod
    def create_file_wrapper(file_path: str, filename: str, content_type: str = None) -> URLFileWrapper:
        """Create a URLFileWrapper for the given file."""
        return URLFileWrapper(file_path, filename, content_type)


class ServiceRouter:
    """Handles service capability decisions and routing logic."""

    def __init__(self):
        self.service_capabilities = self._load_service_capabilities()

    def _load_service_capabilities(self) -> Dict[str, Dict]:
        """Load service capabilities from configuration."""
        return {
            "gotenberg": {
                "supports_direct_url": True,
                "supported_url_formats": ["html", "pdf", "auto"],
                "supported_input_formats": ["html"],
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

    def can_service_handle_url_directly(self, service: str, target_format: str) -> bool:
        """Check if service can handle URL directly for target format."""
        caps = self.service_capabilities.get(service, {})
        return caps.get("supports_direct_url", False) and \
               target_format in caps.get("supported_url_formats", [])

    def can_service_handle_format(self, service: str, input_format: str) -> bool:
        """Check if service can handle a specific input format."""
        caps = self.service_capabilities.get(service, {})
        return input_format in caps.get("supported_input_formats", [])

    def find_best_service(self, input_format: str, output_format: str) -> ConversionService:
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

    def get_conversion_path(self, input_format: str, output_format: str, service: ConversionService) -> Dict[str, Any]:
        """Determine optimal conversion path for given formats and service."""
        use_direct_url = self.can_service_handle_url_directly(service.value, output_format)
        can_handle_format = self.can_service_handle_format(service.value, input_format)

        return {
            "service": service,
            "use_direct_url": use_direct_url,
            "can_handle_format": can_handle_format,
            "requires_temp_file": not use_direct_url,
            "conversion_path": "direct_url" if use_direct_url else "temp_file_conversion"
        }


class URLProcessor:
    """Main orchestrator for URL-based document processing."""

    def __init__(self):
        self.analyzer = ContentAnalyzer()
        self.fetcher = URLFetcher()
        self.file_manager = FileManager()
        self.router = ServiceRouter()

    def _validate_url(self, url: str) -> None:
        """Validate URL format and protocol."""
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

    async def _fetch_to_temp_file(self, url: str, user_agent: Optional[str] = None) -> Tuple[URLFileWrapper, Dict[str, Any]]:
        """Fetch URL to temp file and return wrapper with metadata."""
        try:
            # Fetch content
            fetch_result = await self.fetcher.fetch_content(url, user_agent=user_agent)

            # Detect actual format from content
            detected_format = self.analyzer.detect_format_from_content(
                fetch_result['content'],
                fetch_result.get('content_type', ''),
                url
            )

            # Generate filename
            filename = self.file_manager.generate_temp_filename(url, fetch_result.get('content_type', ''))

            # Save to temp file
            temp_path = await self.file_manager.save_to_temp_file(fetch_result['content'], filename)

            # Create file wrapper
            content_type = fetch_result.get('content_type', f'application/{detected_format}')
            file_wrapper = self.file_manager.create_file_wrapper(str(temp_path), filename, content_type)

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
        detected_format = self.analyzer.detect_format_from_url(url)

        # Find best service for this conversion
        primary_service = self.router.find_best_service(detected_format, target_format)

        # Get conversion path details
        path_info = self.router.get_conversion_path(detected_format, target_format, primary_service)

        return {
            "detected_format": detected_format,
            **path_info
        }

    async def process_url(self, url: str, target_format: str, user_agent: Optional[str] = None) -> ConversionInput:
        """
        Main entry point - process URL and return ConversionInput ready for conversion pipeline.

        Args:
            url: The URL to process
            target_format: Desired output format
            user_agent: Optional custom User-Agent string

        Returns:
            ConversionInput ready for the conversion pipeline

        Raises:
            HTTPException: If URL is invalid or processing fails
        """
        # Validate URL
        self._validate_url(url)

        # Detect content format from URL
        detected_format = self.analyzer.detect_format_from_url(url)

        # Check if this is a passthrough conversion
        if detected_format == target_format and detected_format in PASSTHROUGH_FORMATS:
            metadata = {
                'source': 'url',
                'original_url': url,
                'detected_format': detected_format,
                'conversion_path': 'direct_url',
                'passthrough_conversion': True
            }
            return DirectURLInput(url, metadata)
        elif detected_format == target_format and detected_format not in PASSTHROUGH_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Passthrough not allowed for format {detected_format}. Use a different output format."
            )

        # Get optimal conversion path
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
            temp_file_wrapper, fetch_metadata = await self._fetch_to_temp_file(url, user_agent)

            # Combine metadata
            metadata = {
                'source': 'url',
                'original_url': url,
                'detected_format': path_info["detected_format"],
                'conversion_path': 'temp_file',
                **fetch_metadata
            }

            return TempFileInput(temp_file_wrapper, metadata)


# Global instance for backward compatibility
_url_processor = None

def get_url_processor() -> URLProcessor:
    """Get the global URL processor instance."""
    global _url_processor
    if _url_processor is None:
        _url_processor = URLProcessor()
    return _url_processor


# Backward compatibility functions
async def fetch_url_content(url: str, timeout: int = DEFAULT_TIMEOUT, use_scrapy: bool = False, user_agent: Optional[str] = None) -> Dict[str, Any]:
    """Backward compatibility function for url_fetcher.fetch_url_content."""
    processor = get_url_processor()
    return await processor.fetcher.fetch_content(url, timeout, user_agent)


async def fetch_url_to_temp_file(url: str, timeout: int = DEFAULT_TIMEOUT, use_scrapy: bool = False, user_agent: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    """Backward compatibility function for url_fetcher.fetch_url_to_temp_file."""
    processor = get_url_processor()
    file_wrapper, metadata = await processor._fetch_to_temp_file(url, user_agent)
    return file_wrapper.file_path, metadata


def detect_content_format(content: bytes, content_type: str = '', url: str = '') -> str:
    """Backward compatibility function for url_fetcher.detect_content_format."""
    processor = get_url_processor()
    return processor.analyzer.detect_format_from_content(content, content_type, url)


# Ensure temp directory exists
os.makedirs(TEMP_DIR, exist_ok=True)