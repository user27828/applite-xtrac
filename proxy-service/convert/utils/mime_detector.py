"""
Unified MIME type detection utility.

This module provides a centralized MIME type detection system that handles
multiple detection methods with consistent priority ordering and fallbacks.
"""

import logging
import mimetypes
from pathlib import Path
from typing import Optional, Union, Tuple

# Try to import python-magic for content-based detection
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    magic = None
    MAGIC_AVAILABLE = False

# Set up logging
logger = logging.getLogger(__name__)

# Comprehensive MIME type mappings for common document formats
MIME_TYPE_MAPPINGS = {
    # Document formats
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "odt": "application/vnd.oasis.opendocument.text",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "odp": "application/vnd.oasis.opendocument.presentation",
    "rtf": "application/rtf",

    # Text formats
    "txt": "text/plain",
    "html": "text/html",
    "htm": "text/html",
    "md": "text/markdown",
    "tex": "application/x-tex",
    "latex": "application/x-latex",

    # Apple formats
    "pages": "application/vnd.apple.pages",
    "numbers": "application/vnd.apple.numbers",
    "key": "application/vnd.apple.keynote",

    # Email formats
    "eml": "message/rfc822",
    "msg": "application/vnd.ms-outlook",

    # Archive formats
    "zip": "application/zip",
    "rar": "application/x-rar-compressed",

    # Image formats (for OCR/document processing)
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
    "tif": "image/tiff",

    # JSON and structured data
    "json": "application/json",
    "xml": "application/xml",
    "csv": "text/csv",
}

# Reverse mapping for content-type to format detection
CONTENT_TYPE_TO_FORMAT = {v: k for k, v in MIME_TYPE_MAPPINGS.items()}


class MimeTypeDetector:
    """
    Unified MIME type detector with multiple detection methods and consistent fallbacks.

    Detection priority order:
    1. Content-based detection (python-magic) - most accurate
    2. Extension-based detection (mimetypes module)
    3. Custom mappings and overrides
    4. Generic fallbacks
    """

    def __init__(self):
        """Initialize the MIME type detector."""
        # Initialize mimetypes with additional mappings
        mimetypes.init()

        # Add custom MIME type mappings
        for ext, mime_type in MIME_TYPE_MAPPINGS.items():
            mimetypes.add_type(mime_type, f".{ext}")

    def detect_from_content(
        self,
        content: bytes,
        filename: Optional[str] = None,
        expected_format: Optional[str] = None
    ) -> str:
        """
        Detect MIME type from file content using python-magic.

        Args:
            content: Raw file content bytes
            filename: Optional filename for context
            expected_format: Optional expected output format for overrides

        Returns:
            Detected MIME type string
        """
        if not MAGIC_AVAILABLE or not content:
            return None

        try:
            # Use python-magic for content-based detection
            detected_mime = magic.from_buffer(content, mime=True)

            if detected_mime:
                # Apply format-specific overrides
                if expected_format and self._should_override_magic(detected_mime, expected_format):
                    override_mime = MIME_TYPE_MAPPINGS.get(expected_format)
                    if override_mime:
                        logger.debug(f"Overriding magic detection {detected_mime} -> {override_mime} for format {expected_format}")
                        return override_mime

                logger.debug(f"Content-based detection: {detected_mime}")
                return detected_mime

        except Exception as e:
            logger.debug(f"Content-based detection failed: {e}")

        return None

    def detect_from_extension(self, filename: str) -> str:
        """
        Detect MIME type from file extension using mimetypes module.

        Args:
            filename: Filename or extension

        Returns:
            Detected MIME type string or None
        """
        if not filename:
            return None

        try:
            # Extract extension if full path provided
            if "/" in filename or "\\" in filename:
                filename = Path(filename).name

            # Remove leading dot if present
            if filename.startswith("."):
                extension = filename[1:]
            else:
                extension = Path(filename).suffix[1:].lower()

            if not extension:
                return None

            # Use mimetypes for extension-based detection
            mime_type, _ = mimetypes.guess_type(f"file.{extension}")

            if mime_type:
                # Handle special cases
                mime_type = self._normalize_mime_type(mime_type, extension)
                logger.debug(f"Extension-based detection: {extension} -> {mime_type}")
                return mime_type

        except Exception as e:
            logger.debug(f"Extension-based detection failed: {e}")

        return None

    def detect_from_mapping(self, format_or_extension: str) -> str:
        """
        Detect MIME type from custom mapping table.

        Args:
            format_or_extension: File format or extension

        Returns:
            MIME type string or None
        """
        if not format_or_extension:
            return None

        # Remove leading dot if present
        format_clean = format_or_extension.lstrip(".")

        # Look up in custom mappings
        mime_type = MIME_TYPE_MAPPINGS.get(format_clean.lower())
        if mime_type:
            logger.debug(f"Mapping-based detection: {format_clean} -> {mime_type}")
            return mime_type

        return None

    def get_mime_type(
        self,
        content: Optional[bytes] = None,
        filename: Optional[str] = None,
        extension: Optional[str] = None,
        expected_format: Optional[str] = None
    ) -> str:
        """
        Get MIME type using multiple detection methods with priority ordering.

        Args:
            content: Optional raw file content for content-based detection
            filename: Optional filename for extension-based detection
            extension: Optional file extension (alternative to filename)
            expected_format: Optional expected output format for overrides

        Returns:
            MIME type string with fallback to application/octet-stream
        """
        detected_mime = None

        # Method 1: Content-based detection (most accurate)
        if content:
            detected_mime = self.detect_from_content(content, filename, expected_format)

        # Method 2: Extension-based detection
        if not detected_mime:
            if filename:
                detected_mime = self.detect_from_extension(filename)
            elif extension:
                detected_mime = self.detect_from_extension(f"file.{extension}")

        # Method 3: Custom mapping fallback
        if not detected_mime:
            lookup_key = expected_format or extension
            if lookup_key:
                detected_mime = self.detect_from_mapping(lookup_key)

        # Method 4: Generic fallback
        if not detected_mime:
            if expected_format:
                detected_mime = f"application/{expected_format}"
            else:
                detected_mime = "application/octet-stream"

        logger.debug(f"Final MIME type detection: {detected_mime}")
        return detected_mime

    def get_format_from_mime_type(self, mime_type: str) -> Optional[str]:
        """
        Get file format from MIME type.

        Args:
            mime_type: MIME type string

        Returns:
            File format/extension or None
        """
        if not mime_type:
            return None

        # Clean up MIME type (remove charset, etc.)
        mime_clean = mime_type.lower().split(";")[0].strip()

        # Look up in reverse mapping
        return CONTENT_TYPE_TO_FORMAT.get(mime_clean)

    def _should_override_magic(self, detected_mime: str, expected_format: str) -> bool:
        """
        Determine if magic detection should be overridden for specific cases.

        Args:
            detected_mime: MIME type detected by magic
            expected_format: Expected output format

        Returns:
            True if override should be applied
        """
        # Override cases where magic detection is known to be inaccurate
        override_cases = {
            "text/plain": ["html", "md", "tex", "latex"],
            "application/octet-stream": ["pdf", "docx", "xlsx", "pptx"]
        }

        return expected_format in override_cases.get(detected_mime, [])

    def _normalize_mime_type(self, mime_type: str, extension: str) -> str:
        """
        Normalize MIME type for consistency.

        Args:
            mime_type: Raw MIME type from mimetypes
            extension: File extension

        Returns:
            Normalized MIME type
        """
        # Handle special cases
        if extension == "tex" and mime_type == "text/x-tex":
            return "application/x-tex"

        if extension == "latex" and mime_type == "text/x-tex":
            return "application/x-latex"

        return mime_type


# Global detector instance
_detector_instance = None

def get_mime_detector() -> MimeTypeDetector:
    """Get the global MIME type detector instance."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = MimeTypeDetector()
    return _detector_instance

def get_mime_type(
    content: Optional[bytes] = None,
    filename: Optional[str] = None,
    extension: Optional[str] = None,
    expected_format: Optional[str] = None
) -> str:
    """
    Convenience function to get MIME type using the global detector.

    Args:
        content: Optional raw file content for content-based detection
        filename: Optional filename for extension-based detection
        extension: Optional file extension (alternative to filename)
        expected_format: Optional expected output format for overrides

    Returns:
        MIME type string
    """
    detector = get_mime_detector()
    return detector.get_mime_type(content, filename, extension, expected_format)

def get_format_from_mime_type(mime_type: str) -> Optional[str]:
    """
    Convenience function to get format from MIME type.

    Args:
        mime_type: MIME type string

    Returns:
        File format/extension or None
    """
    detector = get_mime_detector()
    return detector.get_format_from_mime_type(mime_type)
