"""
HTML Processing Utilities for PyConvert Service.

This module provides utilities for HTML content processing, validation, and formatting.
"""

import re
import logging
from typing import Optional, Tuple
from bs4 import BeautifulSoup

# Import centralized logging configuration
from .logging_config import get_logger

logger = get_logger()


def detect_html_structure(html_content: str) -> Tuple[bool, bool, bool]:
    """
    Detect the structure of HTML content.

    Args:
        html_content: The HTML content to analyze

    Returns:
        Tuple of (has_doctype, has_html_tag, has_body_tag)
    """
    if not html_content:
        return False, False, False

    soup = BeautifulSoup(html_content, 'html.parser')

    has_doctype = bool(soup.find(string=lambda text: isinstance(text, str) and '<!DOCTYPE' in text))
    has_html = bool(soup.find('html'))
    has_body = bool(soup.find('body'))

    return has_doctype, has_html, has_body


def is_full_html_document(html_content: str) -> bool:
    """
    Check if the HTML content is a full HTML document with html and body tags.

    Args:
        html_content: The HTML content to check

    Returns:
        True if it's a full HTML document, False otherwise
    """
    has_html, _, has_body = detect_html_structure(html_content)
    return has_html and has_body


def extract_html_body_content(html_content: str) -> str:
    """
    Extract the content inside the <body> tag from HTML.

    Args:
        html_content: The HTML content to extract from

    Returns:
        The content inside the <body> tag, or the original content if no body tag found
    """
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, 'html.parser')
    body_tag = soup.find('body')

    if body_tag:
        # Return the inner HTML of the body tag
        return ''.join(str(content) for content in body_tag.contents)
    else:
        # No body tag found, return original content
        return html_content


def wrap_html_content(content: str, title: Optional[str] = None) -> str:
    """
    Wrap content in a full HTML document structure.

    Args:
        content: The HTML content to wrap
        title: Optional title for the HTML document

    Returns:
        Full HTML document with proper structure
    """
    if not content:
        content = ""

    title_tag = f"<title>{title}</title>" if title else "<title>Document</title>"

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {title_tag}
</head>
<body>
{content}
</body>
</html>"""

    return html_template


def process_html_content(
    html_content: str,
    html_body_wrap: Optional[bool] = None,
    title: Optional[str] = None
) -> str:
    """
    Process HTML content based on the htmlBodyWrap parameter.

    This function analyzes the HTML structure and either:
    - Returns only the HTML snippets WITHOUT <body> and <html> tags (if htmlBodyWrap=False)
    - Wraps the content in proper HTML structure if it's not already wrapped (if htmlBodyWrap=True)

    Args:
        html_content: The HTML content to process
        html_body_wrap: If True, ensures the output is wrapped in <html> and <body> tags
                        If False, returns only the inner content without <html> and <body> tags
                        If None, returns the content as-is
        title: Optional title for the HTML document (only used when wrapping)

    Returns:
        Processed HTML content according to the htmlBodyWrap parameter
    """
    if not html_content:
        if html_body_wrap:
            return wrap_html_content("", title)
        return ""

    # If html_body_wrap is None, return as-is
    if html_body_wrap is None:
        return html_content

    # Check if it's already a full HTML document
    is_full_document = is_full_html_document(html_content)

    if html_body_wrap:
        # Need to ensure it's wrapped
        if is_full_document:
            # Already wrapped, return as-is
            return html_content
        else:
            # Not wrapped, wrap it
            return wrap_html_content(html_content, title)
    else:
        # Need to return unwrapped content
        if is_full_document:
            # Extract content from body tag
            return extract_html_body_content(html_content)
        else:
            # Already unwrapped, return as-is
            return html_content


def normalize_html_content(html_content: str) -> str:
    """
    Normalize HTML content by ensuring consistent formatting and structure.

    Args:
        html_content: The HTML content to normalize

    Returns:
        Normalized HTML content
    """
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, 'html.parser')

    # Pretty print with proper indentation
    return soup.prettify()


def validate_html_content(html_content: str) -> Tuple[bool, Optional[str]]:
    """
    Validate HTML content for basic structural integrity.

    Args:
        html_content: The HTML content to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if HTML is structurally valid
        - error_message: None if valid, otherwise description of the issue
    """
    if not html_content:
        return False, "Empty content"

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Check for basic structure
        if not soup.find():
            return False, "No valid HTML elements found"

        return True, None

    except Exception as e:
        logger.error(f"HTML validation error: {e}")
        return False, f"HTML parsing error: {str(e)}"
