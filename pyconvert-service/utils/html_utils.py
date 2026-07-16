"""
HTML Processing Utilities for PyConvert Service.

This module provides utilities for HTML content processing, validation,
normalization, and formatting.
"""

from typing import Optional, Tuple
from bs4 import BeautifulSoup, Tag

# Import centralized logging configuration
from .logging_config import get_logger

logger = get_logger()


PANDOC_DOCX_METADATA_NAMES = {"author", "date", "keywords"}
PANDOC_DOCX_SEMANTIC_CONTAINER_TAGS = {
    "header",
    "main",
    "section",
    "article",
    "aside",
    "footer",
    "nav",
}
PANDOC_DOCX_BLOCK_LEVEL_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "details",
    "dialog",
    "div",
    "dl",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "ul",
}


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


def normalize_html_for_pandoc_docx(html_content: str) -> str:
    """
    Normalize HTML before Pandoc HTML->DOCX conversion.

    Pandoc's manual explicitly notes that conversions from richer formats can be
    lossy. In practice, resume-style HTML can lose short contact/location lines
    when they are wrapped in semantic containers and text-only ``div`` blocks,
    while ``<title>`` and selected ``<meta>`` tags may surface as unwanted DOCX
    body content. This helper strips those metadata fields and flattens the HTML
    into paragraph-friendly blocks before Pandoc emits DOCX.

    Args:
        html_content: The HTML content to normalize.

    Returns:
        HTML content normalized for Pandoc DOCX output.
    """
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, 'html.parser')

    _strip_pandoc_docx_metadata(soup)
    _flatten_pandoc_docx_semantic_containers(soup)
    _convert_text_only_divs_to_paragraphs(soup)

    return str(soup)


def _strip_pandoc_docx_metadata(soup: BeautifulSoup) -> None:
    """Remove head metadata that Pandoc can echo into DOCX output."""
    head_tag = soup.find('head')
    if not head_tag:
        return

    for meta_tag in head_tag.find_all('meta'):
        meta_name = (meta_tag.get('name') or '').strip().lower()
        if meta_name in PANDOC_DOCX_METADATA_NAMES:
            meta_tag.decompose()

    title_tag = head_tag.find('title')
    if title_tag:
        title_tag.decompose()


def _flatten_pandoc_docx_semantic_containers(soup: BeautifulSoup) -> None:
    """Rename semantic HTML containers to simple div blocks for Pandoc."""
    for tag_name in PANDOC_DOCX_SEMANTIC_CONTAINER_TAGS:
        for tag in soup.find_all(tag_name):
            tag.name = 'div'


def _convert_text_only_divs_to_paragraphs(soup: BeautifulSoup) -> None:
    """Promote short text-only div blocks to paragraphs for DOCX writers."""
    for div_tag in list(soup.find_all('div')):
        if _should_convert_div_to_paragraph(div_tag):
            div_tag.name = 'p'


def _should_convert_div_to_paragraph(div_tag: Tag) -> bool:
    """Return True when a div contains only inline/text content."""
    if div_tag.find_parent('head') is not None:
        return False

    if not div_tag.get_text(strip=True):
        return False

    for descendant in div_tag.find_all(True):
        if descendant.name in PANDOC_DOCX_BLOCK_LEVEL_TAGS:
            return False

    return True


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
