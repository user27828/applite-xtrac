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
from .temp_file_manager import (
    get_temp_manager,
    TempFileManager,
    TempFileInfo,
    cleanup_temp_files,
    cleanup_temp_file
)

# Import centralized logging configuration
from .logging_config import get_logger

logger = get_logger()

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
    Save content to a temporary file using the centralized manager.

    Args:
        content: The content to save
        filename: The filename to use

    Returns:
        The path to the saved file
    """
    manager = get_temp_manager("url_fetcher")
    temp_file = manager.create_temp_file(content=content, filename=filename)
    return temp_file.path


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

    # Save to temp file using centralized manager
    manager = get_temp_manager("url_fetcher")
    temp_file = manager.create_temp_file(content=fetch_result['content'], filename=filename)

    return temp_file.path, fetch_result


def detect_content_format(content: bytes, content_type: str = '', url: str = '') -> str:
    """
    Detect the actual content format from content, content-type, and URL.

    This function uses multiple detection methods with priority:
    1. Content-based detection (using python-magic if available)
    2. Content-type header analysis
    3. URL-based detection as fallback

    Args:
        content: The raw content bytes
        content_type: Content-Type header value
        url: The source URL (for fallback detection)

    Returns:
        Detected format string (e.g., 'pdf', 'docx', 'html')
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
            url_content_type = get_content_type_from_url(url)
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
