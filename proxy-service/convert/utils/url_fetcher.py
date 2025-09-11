"""
URL fetching utilities for document conversion services.

This module provides functionality to fetch remote URLs and prepare them
for conversion by services that don't support direct URL input.
"""

import os
import tempfile
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from urllib.parse import urlparse, urljoin, unquote
import mimetypes
import hashlib

# Try to import magic for content-based detection
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    magic = None
    MAGIC_AVAILABLE = False

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.spiders import Spider
from scrapy.http import Request
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Import unified MIME detector
from .mime_detector import get_mime_type as get_unified_mime_type, get_format_from_mime_type

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_SIZE = 50 * 1024 * 1024  # 50MB
TEMP_DIR = "/tmp/applite-xtrac"

# Ensure temp directory exists
os.makedirs(TEMP_DIR, exist_ok=True)


class URLFetchError(Exception):
    """Custom exception for URL fetching errors."""
    pass


class URLContentSpider(Spider):
    """Scrapy spider for fetching single URL content."""

    name = 'url_fetcher'

    def __init__(self, url: str, callback, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_url = url
        self.result_callback = callback
        self.content = None
        self.content_type = None
        self.final_url = None

    def start_requests(self):
        """Start the crawling process."""
        yield Request(
            self.start_url,
            callback=self.parse,
            headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )

    def parse(self, response):
        """Parse the response and store content."""
        self.content = response.body
        self.content_type = response.headers.get('Content-Type', b'').decode('utf-8', errors='ignore')
        self.final_url = response.url

        if self.result_callback:
            self.result_callback({
                'content': self.content,
                'content_type': self.content_type,
                'final_url': self.final_url,
                'status': response.status,
                'headers': dict(response.headers)
            })


def create_session_with_retries() -> requests.Session:
    """Create a requests session with retry configuration."""
    session = requests.Session()

    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],  # Changed from method_whitelist
        backoff_factor=1
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


async def fetch_url_with_scrapy(url: str, timeout: int = DEFAULT_TIMEOUT, user_agent: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch URL content using Scrapy.

    Args:
        url: The URL to fetch
        timeout: Timeout in seconds
        user_agent: Custom User-Agent string to use for the request

    Returns:
        Dict containing content, content_type, final_url, status, headers

    Raises:
        URLFetchError: If fetching fails
    """
    result = {}

    def result_callback(data):
        result.update(data)

    try:
        # Configure Scrapy settings
        scrapy_user_agent = user_agent or 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        settings = {
            'USER_AGENT': scrapy_user_agent,
            'ROBOTSTXT_OBEY': True,
            'DOWNLOAD_DELAY': 1,
            'CONCURRENT_REQUESTS': 1,
            'DOWNLOAD_TIMEOUT': timeout,
            'LOG_LEVEL': 'ERROR',  # Reduce log noise
            'TWISTED_REACTOR': None,  # Disable Twisted reactor to avoid conflicts
        }

        # Create and run crawler in a separate thread to avoid event loop conflicts
        def run_crawler():
            try:
                from scrapy.utils.test import get_crawler
                from twisted.internet import reactor, defer
                from twisted.internet.threads import deferToThread
                
                # Use a simpler approach - just use requests as fallback for now
                # Scrapy has complex event loop requirements that conflict with FastAPI
                raise Exception("Scrapy disabled due to event loop conflicts")
                
            except Exception as e:
                # If Scrapy fails, we'll fall back to requests
                raise e

        # For now, let's disable Scrapy and use requests directly
        # This avoids the complex event loop issues
        raise URLFetchError("Scrapy temporarily disabled - using requests fallback")

    except URLFetchError:
        raise  # Re-raise our custom errors
    except Exception as e:
        logger.warning(f"Scrapy fetch failed, falling back to requests: {e}")
        raise URLFetchError(f"Failed to fetch URL with Scrapy: {str(e)}")


async def fetch_url_with_requests(url: str, timeout: int = DEFAULT_TIMEOUT, user_agent: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch URL content using requests (fallback method).

    Args:
        url: The URL to fetch
        timeout: Timeout in seconds
        user_agent: Custom User-Agent string to use for the request

    Returns:
        Dict containing content, content_type, final_url, status, headers

    Raises:
        URLFetchError: If fetching fails
    """
    try:
        session = create_session_with_retries()

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
                raise URLFetchError(f"Content size exceeds maximum limit of {DEFAULT_MAX_SIZE} bytes")

        return {
            'content': content,
            'content_type': response.headers.get('Content-Type', ''),
            'final_url': response.url,
            'status': response.status_code,
            'headers': dict(response.headers)
        }

    except requests.RequestException as e:
        logger.error(f"Requests fetch failed for {url}: {e}")
        raise URLFetchError(f"Failed to fetch URL with requests: {str(e)}")


async def fetch_url_content(url: str, timeout: int = DEFAULT_TIMEOUT, use_scrapy: bool = False, user_agent: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch URL content using the best available method.

    Args:
        url: The URL to fetch
        timeout: Timeout in seconds
        use_scrapy: Whether to prefer Scrapy over requests
        user_agent: Custom User-Agent string to use for the request

    Returns:
        Dict containing content, content_type, final_url, status, headers

    Raises:
        URLFetchError: If fetching fails
    """
    if not url or not isinstance(url, str):
        raise URLFetchError("Invalid URL provided")

    # Validate URL format
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise URLFetchError("Invalid URL format")
        if parsed.scheme not in ['http', 'https']:
            raise URLFetchError("Only HTTP and HTTPS URLs are supported")
    except Exception as e:
        raise URLFetchError(f"URL validation failed: {str(e)}")

    # Try Scrapy first if requested
    if use_scrapy:
        try:
            return await fetch_url_with_scrapy(url, timeout, user_agent)
        except URLFetchError as e:
            logger.warning(f"Scrapy fetch failed, falling back to requests: {e}")
            # Fall through to requests

    # Fallback to requests
    return await fetch_url_with_requests(url, timeout, user_agent)


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


async def save_content_to_temp_file(content: bytes, filename: str) -> str:
    """
    Save content to a temporary file.

    Args:
        content: The content to save
        filename: The filename to use

    Returns:
        The path to the saved file
    """
    temp_path = os.path.join(TEMP_DIR, filename)

    try:
        with open(temp_path, 'wb') as f:
            f.write(content)

        logger.info(f"Saved content to temporary file: {temp_path}")
        return temp_path

    except Exception as e:
        logger.error(f"Failed to save content to temp file: {e}")
        raise URLFetchError(f"Failed to save content: {str(e)}")


async def fetch_url_to_temp_file(url: str, timeout: int = DEFAULT_TIMEOUT, use_scrapy: bool = False, user_agent: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    """
    Fetch URL content and save to a temporary file.

    Args:
        url: The URL to fetch
        timeout: Timeout in seconds
        use_scrapy: Whether to prefer Scrapy over requests

    Returns:
        Tuple of (temp_file_path, fetch_metadata)

    Raises:
        URLFetchError: If fetching or saving fails
    """
    # Fetch the content
    fetch_result = await fetch_url_content(url, timeout, use_scrapy, user_agent)

    # Generate filename
    content_type = fetch_result.get('content_type', '')
    filename = generate_temp_filename(url, content_type)

    # Save to temp file
    temp_path = await save_content_to_temp_file(fetch_result['content'], filename)

    return temp_path, fetch_result


def cleanup_temp_file(file_path: str):
    """Clean up a temporary file."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup temp file {file_path}: {e}")


async def cleanup_temp_files_async(file_paths: list):
    """Clean up multiple temporary files asynchronously."""
    for path in file_paths:
        cleanup_temp_file(path)


class TempFileManager:
    """Context manager for temporary file management."""

    def __init__(self):
        self.temp_files = []

    def add_file(self, file_path: str):
        """Add a file to be managed."""
        self.temp_files.append(file_path)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up all managed files."""
        await cleanup_temp_files_async(self.temp_files)
        self.temp_files.clear()


# MIME type to format mapping
MIME_TYPE_MAPPING = {
    # Web formats
    'text/html': 'html',
    'application/xhtml+xml': 'html',
    'text/xml': 'xml',
    'application/xml': 'xml',
    'application/json': 'json',
    'text/plain': 'txt',
    'text/markdown': 'md',
    
    # Document formats
    'application/pdf': 'pdf',
    'application/msword': 'doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'application/vnd.ms-excel': 'xls',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
    'application/vnd.ms-powerpoint': 'ppt',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
    'application/rtf': 'rtf',
    'text/rtf': 'rtf',
    
    # OpenDocument formats
    'application/vnd.oasis.opendocument.text': 'odt',
    'application/vnd.oasis.opendocument.spreadsheet': 'ods',
    'application/vnd.oasis.opendocument.presentation': 'odp',
    
    # Other formats
    'application/epub+zip': 'epub',
    'application/x-tex': 'tex',
    'application/x-latex': 'tex',
    'text/x-tex': 'tex',
    'text/x-latex': 'tex',
    
    # Email formats
    'message/rfc822': 'eml',
    'application/vnd.ms-outlook': 'msg',
    
    # Apple formats
    'application/vnd.apple.pages': 'pages',
    'application/vnd.apple.numbers': 'numbers',
    'application/vnd.apple.keynote': 'key',
}

# File extension to format mapping (fallback)
EXTENSION_MAPPING = {
    '.html': 'html', '.htm': 'html',
    '.xml': 'xml',
    '.json': 'json',
    '.txt': 'txt', '.text': 'txt',
    '.md': 'md', '.markdown': 'md',
    '.pdf': 'pdf',
    '.doc': 'doc',
    '.docx': 'docx',
    '.xls': 'xls',
    '.xlsx': 'xlsx',
    '.ppt': 'ppt',
    '.pptx': 'pptx',
    '.rtf': 'rtf',
    '.odt': 'odt',
    '.ods': 'ods',
    '.odp': 'odp',
    '.epub': 'epub',
    '.tex': 'tex', '.latex': 'tex',
    '.eml': 'eml',
    '.msg': 'msg',
    '.pages': 'pages',
    '.numbers': 'numbers',
    '.key': 'key',
}


# Utility functions for integration with conversion pipeline
def detect_content_format(content: bytes, content_type: str, url: str) -> str:
    """
    Detect the content format from content, content-type, and URL using libraries.
    
    Uses python-magic for content-based detection, mimetypes for extension detection,
    and comprehensive mappings for format conversion.

    Args:
        content: The raw content bytes
        content_type: The content-type header
        url: The original URL

    Returns:
        Detected format (e.g., 'html', 'pdf', 'txt', etc.)
    """
    detected_mime = None
    
    # Method 1: Use content-type header if available
    if content_type:
        content_type_lower = content_type.lower().split(';')[0].strip()  # Remove charset, etc.
        if content_type_lower in MIME_TYPE_MAPPING:
            return MIME_TYPE_MAPPING[content_type_lower]
        
        # Store for potential use
        detected_mime = content_type_lower
    
    # Method 2: Use unified MIME detector for content-based detection (most reliable)
    if not detected_mime and content:
        try:
            # Use unified MIME detector with content
            unified_mime = get_unified_mime_type(content=content, filename=url)
            if unified_mime and unified_mime in MIME_TYPE_MAPPING:
                return MIME_TYPE_MAPPING[unified_mime]
            
            # If unified detector found something different, use it
            if unified_mime and unified_mime != detected_mime:
                detected_mime = unified_mime
                
        except Exception as e:
            logger.debug(f"Unified MIME detection failed: {e}")
    
    # Method 3: Use mimetypes for extension-based detection
    if not detected_mime:
        try:
            parsed = urlparse(url)
            path = unquote(parsed.path)
            
            # Use unified MIME detector to guess from extension
            guessed_mime = get_unified_mime_type(filename=path)
            if guessed_mime:
                detected_mime = guessed_mime
                if guessed_mime in MIME_TYPE_MAPPING:
                    return MIME_TYPE_MAPPING[guessed_mime]
        except Exception as e:
            logger.debug(f"MIME detection failed: {e}")
    
    # Method 4: Check our extension mapping as fallback
    if not detected_mime:
        try:
            parsed = urlparse(url)
            path = unquote(parsed.path).lower()
            
            for ext, fmt in EXTENSION_MAPPING.items():
                if path.endswith(ext):
                    return fmt
        except Exception as e:
            logger.debug(f"Extension mapping failed: {e}")
    
    # Method 5: Try to map detected MIME type to our formats
    if detected_mime:
        # Try partial matches for common patterns
        detected_lower = detected_mime.lower()
        
        # Check for common MIME type patterns
        if 'html' in detected_lower:
            return 'html'
        elif 'pdf' in detected_lower:
            return 'pdf'
        elif 'json' in detected_lower:
            return 'json'
        elif 'xml' in detected_lower:
            return 'xml'
        elif 'text' in detected_lower:
            return 'txt'
        elif 'msword' in detected_lower:
            return 'doc'
        elif 'wordprocessingml' in detected_lower:
            return 'docx'
        elif 'excel' in detected_lower or 'spreadsheetml' in detected_lower:
            return 'xlsx'
        elif 'powerpoint' in detected_lower or 'presentationml' in detected_lower:
            return 'pptx'
        elif 'opendocument.text' in detected_lower:
            return 'odt'
        elif 'opendocument.spreadsheet' in detected_lower:
            return 'ods'
        elif 'opendocument.presentation' in detected_lower:
            return 'odp'
        elif 'rtf' in detected_lower:
            return 'rtf'
        elif 'epub' in detected_lower:
            return 'epub'
        elif 'tex' in detected_lower or 'latex' in detected_lower:
            return 'tex'
    
    # Final fallback: default to HTML for web content
    logger.debug(f"Could not detect format for URL: {url}, content_type: {content_type}, detected_mime: {detected_mime}")
    return 'html'


def should_use_url_fetch(service: str, input_format: str, has_url_input: bool = False) -> bool:
    """
    Determine if URL fetching should be used for a service and format.

    Args:
        service: The service name
        input_format: The input format
        has_url_input: Whether the input is a URL (not a file)

    Returns:
        True if URL fetching should be used
    """
    # Services that don't support direct URL input
    services_needing_fetch = {'unstructured-io', 'libreoffice', 'pandoc'}
    
    # If we have URL input and the service doesn't support direct URLs, we need to fetch
    if has_url_input and service in services_needing_fetch:
        return True
    
    # For file inputs, only fetch if it's a format that typically comes from URLs
    # and the service doesn't support direct processing
    url_formats = {'html', 'auto'}
    return service in services_needing_fetch and input_format in url_formats
