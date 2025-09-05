"""
HTML file validation.

Provides robust validation for HTML files with support for both full documents
and HTML content fragments.
"""

import re
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def validate_html(file_path: str, full: Optional[bool] = None) -> bool:
    """
    Validate HTML file content.

    Args:
        file_path: Path to the HTML file
        full: If True, expect full HTML document with <html> and <body> tags.
              If False or None, allow HTML content fragments with at least one tag.

    Returns:
        bool: True if validation passes

    Raises:
        ValueError: If validation fails
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception as e:
        raise ValueError(f"Failed to read HTML file: {e}")

    # Remove whitespace and comments for cleaner parsing
    content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    content = re.sub(r'\s+', ' ', content).strip()

    if not content:
        raise ValueError("HTML file is empty")

    if full:
        # Full HTML document validation
        return _validate_full_html(content)
    else:
        # HTML content fragment validation (default when full is None or False)
        return _validate_html_content(content)

def _validate_full_html(content: str) -> bool:
    """
    Validate full HTML document.

    Requires:
    - <html> tag
    - <body> tag
    - Content in <body>
    """
    # Check for HTML tag (case insensitive)
    if not re.search(r'<html[^>]*>', content, re.IGNORECASE):
        raise ValueError("Full HTML document must contain <html> tag")

    # Check for body tag
    if not re.search(r'<body[^>]*>', content, re.IGNORECASE):
        raise ValueError("Full HTML document must contain <body> tag")

    # Extract body content
    body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.IGNORECASE | re.DOTALL)
    if not body_match:
        raise ValueError("Full HTML document must have properly closed <body> tag")

    body_content = body_match.group(1).strip()
    if not body_content:
        raise ValueError("HTML document body must contain content")

    # Check for at least one meaningful tag in body
    if not re.search(r'<[^>]+>', body_content):
        raise ValueError("HTML document body must contain at least one HTML tag")

    return True

def _validate_html_content(content: str) -> bool:
    """
    Validate HTML content fragment.

    Requires:
    - At least one HTML tag
    - Some content (text or tags)
    """
    # Check for at least one HTML tag
    if not re.search(r'<[^>]+>', content):
        raise ValueError("HTML content must contain at least one HTML tag")

    # Check for actual content (not just empty tags)
    # Remove all tags and check if there's remaining text
    text_content = re.sub(r'<[^>]+>', '', content).strip()

    if not text_content:
        raise ValueError("HTML content must contain actual text content")

    return True
