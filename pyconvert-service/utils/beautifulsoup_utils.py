"""
BeautifulSoup Processing Utilities for PyConvert Service.

This module provides comprehensive HTML processing and cleaning capabilities using BeautifulSoup.
It extends the basic HTML utilities with advanced cleaning, extraction, and transformation features.

Features:
- HTML cleaning and sanitization
- Content extraction (text, titles, metadata)
- Tag and attribute filtering
- Link processing and validation
- HTML structure analysis and repair
- Content transformation and formatting

Usage:
    from utils.beautifulsoup_utils import BeautifulSoupProcessor

    processor = BeautifulSoupProcessor()
    cleaned_html = processor.clean_html(html_content, remove_scripts=True, prettify=True)
"""

import re
import logging
from typing import Optional, Dict, List, Set, Tuple, Any
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup, Comment, NavigableString

# Import centralized logging configuration
from .logging_config import get_logger

logger = get_logger()


class BeautifulSoupProcessor:
    """
    Advanced HTML processing and cleaning using BeautifulSoup.

    This class provides a comprehensive set of HTML processing capabilities
    for cleaning, extracting, and transforming HTML content.
    """

    def __init__(self, parser: str = "html.parser"):
        """
        Initialize the BeautifulSoup processor.

        Args:
            parser: HTML parser to use ('html.parser', 'lxml', 'html5lib')
        """
        self.parser = parser
        self.soup = None

    def load_html(self, html_content: str) -> bool:
        """
        Load HTML content into the processor.

        Args:
            html_content: The HTML content to process

        Returns:
            True if loaded successfully, False otherwise
        """
        if not html_content:
            return False

        try:
            self.soup = BeautifulSoup(html_content, self.parser)
            return True
        except Exception as e:
            logger.error(f"Failed to parse HTML: {e}")
            return False

    def clean_html(
        self,
        html_content: str,
        remove_scripts: bool = True,
        remove_styles: bool = False,
        remove_comments: bool = True,
        remove_empty_tags: bool = False,
        remove_attrs: Optional[List[str]] = None,
        allowed_tags: Optional[Set[str]] = None,
        allowed_attrs: Optional[Dict[str, Set[str]]] = None,
        prettify: bool = True
    ) -> str:
        """
        Clean HTML content with various filtering options.

        Args:
            html_content: The HTML content to clean
            remove_scripts: Remove <script> tags
            remove_styles: Remove <style> tags and style attributes
            remove_comments: Remove HTML comments
            remove_empty_tags: Remove tags with no content
            remove_attrs: List of attributes to remove from all tags
            allowed_tags: Set of allowed tag names (whitelist)
            allowed_attrs: Dict mapping tag names to allowed attributes
            prettify: Format the output HTML nicely

        Returns:
            Cleaned HTML content
        """
        if not self.load_html(html_content):
            return html_content

        # Remove scripts
        if remove_scripts:
            for script in self.soup.find_all('script'):
                script.decompose()

        # Remove styles
        if remove_styles:
            for style in self.soup.find_all('style'):
                style.decompose()
            # Remove style attributes
            for tag in self.soup.find_all(attrs={'style': True}):
                del tag['style']

        # Remove comments
        if remove_comments:
            for comment in self.soup.find_all(text=lambda text: isinstance(text, Comment)):
                comment.extract()

        # Remove specified attributes
        if remove_attrs:
            for tag in self.soup.find_all():
                for attr in remove_attrs:
                    if attr in tag.attrs:
                        del tag[attr]

        # Filter allowed tags
        if allowed_tags:
            for tag in self.soup.find_all():
                if tag.name not in allowed_tags:
                    tag.unwrap()  # Remove tag but keep content

        # Filter allowed attributes
        if allowed_attrs:
            for tag in self.soup.find_all():
                if tag.name in allowed_attrs:
                    allowed = allowed_attrs[tag.name]
                    attrs_to_remove = [attr for attr in tag.attrs if attr not in allowed]
                    for attr in attrs_to_remove:
                        del tag[attr]
                else:
                    # Remove all attributes if tag not in allowed_attrs
                    tag.attrs = {}

        # Remove empty tags
        if remove_empty_tags:
            self._remove_empty_tags()

        # Return formatted HTML
        if prettify:
            return self.soup.prettify()
        else:
            return str(self.soup)

    def extract_text(
        self,
        html_content: str,
        separator: str = '\n',
        strip: bool = True,
        preserve_links: bool = False
    ) -> str:
        """
        Extract plain text content from HTML.

        Args:
            html_content: The HTML content to extract from
            separator: String to join text elements
            strip: Whether to strip whitespace
            preserve_links: Whether to include link URLs in text

        Returns:
            Extracted plain text
        """
        if not self.load_html(html_content):
            return ""

        if preserve_links:
            # Replace links with their text + URL
            for link in self.soup.find_all('a', href=True):
                link.string = f"{link.get_text()} [{link['href']}]"

        text = self.soup.get_text(separator=separator, strip=strip)
        return text

    def extract_title(self, html_content: str) -> Optional[str]:
        """
        Extract the page title from HTML.

        Args:
            html_content: The HTML content to extract from

        Returns:
            Page title or None if not found
        """
        if not self.load_html(html_content):
            return None

        title_tag = self.soup.find('title')
        if title_tag:
            return title_tag.get_text().strip()
        return None

    def extract_metadata(self, html_content: str) -> Dict[str, Any]:
        """
        Extract metadata from HTML (title, description, keywords, etc.).

        Args:
            html_content: The HTML content to extract from

        Returns:
            Dictionary containing extracted metadata
        """
        if not self.load_html(html_content):
            return {}

        metadata = {}

        # Title
        title = self.extract_title(html_content)
        if title:
            metadata['title'] = title

        # Meta tags
        for meta in self.soup.find_all('meta'):
            name = meta.get('name') or meta.get('property') or meta.get('http-equiv')
            content = meta.get('content')
            if name and content:
                metadata[name.lower()] = content

        # Description (common variations)
        if 'description' not in metadata:
            desc_meta = self.soup.find('meta', attrs={'name': 'description'})
            if desc_meta:
                metadata['description'] = desc_meta.get('content', '')

        return metadata

    def extract_links(
        self,
        html_content: str,
        base_url: Optional[str] = None,
        include_text: bool = True,
        filter_patterns: Optional[List[str]] = None
    ) -> List[Dict[str, str]]:
        """
        Extract all links from HTML content.

        Args:
            html_content: The HTML content to extract from
            base_url: Base URL for resolving relative links
            include_text: Whether to include link text
            filter_patterns: List of regex patterns to filter links

        Returns:
            List of dictionaries containing link information
        """
        if not self.load_html(html_content):
            return []

        links = []
        for link in self.soup.find_all('a', href=True):
            href = link['href']

            # Resolve relative URLs
            if base_url and not href.startswith(('http://', 'https://', 'mailto:')):
                href = urljoin(base_url, href)

            # Apply filters
            if filter_patterns:
                if not any(re.search(pattern, href) for pattern in filter_patterns):
                    continue

            link_info = {'url': href}
            if include_text:
                link_info['text'] = link.get_text().strip()

            links.append(link_info)

        return links

    def validate_html(self, html_content: str) -> Tuple[bool, Optional[str]]:
        """
        Validate HTML structure and identify potential issues.

        Args:
            html_content: The HTML content to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not html_content:
            return False, "Empty content"

        try:
            if not self.load_html(html_content):
                return False, "Failed to parse HTML"

            issues = []

            # Check for basic structure
            if not self.soup.find():
                issues.append("No valid HTML elements found")

            # Check for unclosed tags (basic check)
            # This is a simple heuristic - real validation would need html5lib or similar
            open_tags = []
            for tag in self.soup.find_all():
                if tag.name in ['br', 'img', 'input', 'meta', 'link']:
                    continue  # Self-closing tags
                if not tag.name.startswith('/'):
                    open_tags.append(tag.name)

            # Very basic check - in practice, BeautifulSoup handles most unclosed tags
            if len(open_tags) == 0 and self.soup.find():
                issues.append("No structural HTML tags found")

            if issues:
                return False, "; ".join(issues)

            return True, None

        except Exception as e:
            logger.error(f"HTML validation error: {e}")
            return False, f"HTML parsing error: {str(e)}"

    def _remove_empty_tags(self):
        """Remove tags that have no meaningful content."""
        if not self.soup:
            return

        # Find empty tags (tags with no text content and no meaningful attributes)
        for tag in self.soup.find_all():
            # Skip tags that should never be removed
            if tag.name in ['html', 'head', 'body', 'title']:
                continue

            # Check if tag has meaningful content
            has_content = False

            # Check for text content
            if tag.get_text().strip():
                has_content = True

            # Check for meaningful attributes
            meaningful_attrs = ['src', 'href', 'alt', 'title', 'id', 'class']
            if any(attr in tag.attrs for attr in meaningful_attrs):
                has_content = True

            # Check for child elements
            if tag.find_all():
                has_content = True

            # Remove if no meaningful content
            if not has_content:
                tag.decompose()


# Convenience functions for common use cases
def clean_html_basic(html_content: str) -> str:
    """
    Basic HTML cleaning - removes scripts, comments, and prettifies.

    Args:
        html_content: The HTML content to clean

    Returns:
        Cleaned HTML content
    """
    processor = BeautifulSoupProcessor()
    return processor.clean_html(
        html_content,
        remove_scripts=True,
        remove_comments=True,
        prettify=True
    )


def extract_text_only(html_content: str) -> str:
    """
    Extract plain text from HTML, removing all markup.

    Args:
        html_content: The HTML content to extract from

    Returns:
        Plain text content
    """
    processor = BeautifulSoupProcessor()
    return processor.extract_text(html_content)


def sanitize_html(html_content: str) -> str:
    """
    Sanitize HTML by removing potentially dangerous elements and attributes.

    Args:
        html_content: The HTML content to sanitize

    Returns:
        Sanitized HTML content
    """
    # Define allowed tags and attributes for basic HTML sanitization
    allowed_tags = {
        'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'hr', 'div', 'span',
        'table', 'thead', 'tbody', 'tr', 'th', 'td', 'a', 'img'
    }

    allowed_attrs = {
        'a': {'href', 'title'},
        'img': {'src', 'alt', 'title'},
        'table': {'border', 'cellpadding', 'cellspacing'},
        'td': {'colspan', 'rowspan'},
        'th': {'colspan', 'rowspan'}
    }

    processor = BeautifulSoupProcessor()
    return processor.clean_html(
        html_content,
        remove_scripts=True,
        remove_styles=True,
        remove_comments=True,
        allowed_tags=allowed_tags,
        allowed_attrs=allowed_attrs,
        prettify=True
    )