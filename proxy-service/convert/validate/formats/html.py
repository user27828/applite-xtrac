"""
HTML file validation.

Validates HTML files using BeautifulSoup for structure and content checks.
"""

import re
from pathlib import Path
from typing import Optional
import logging

from ..base_validator import TextBasedValidator, ValidationError

logger = logging.getLogger(__name__)


class HTMLValidator(TextBasedValidator):
    """HTML file validator using the base validation framework."""

    def __init__(self):
        super().__init__("html")

    def _validate_content(self, content: str, **options) -> bool:
        """
        Validate HTML file content.

        Args:
            content: HTML content to validate
            **options: Additional validation options

        Returns:
            bool: True if validation passes

        Raises:
            ValidationError: If validation fails
        """
        # Perform basic text content validation
        self._validate_basic_text_content(content)

        # Validate HTML-specific structure
        self._validate_html_structure(content)

        return True

    def _validate_html_structure(self, content: str) -> None:
        """
        Validate HTML document structure.

        Args:
            content: HTML content to validate

        Raises:
            ValidationError: If structure validation fails
        """
        # Check for basic HTML structure
        if not re.search(r'<!DOCTYPE\s+html', content, re.IGNORECASE):
            self.logger.warning("Missing DOCTYPE declaration")

        # Check for html tag
        if not re.search(r'<html', content, re.IGNORECASE):
            raise ValidationError(
                "Missing <html> tag",
                format_type=self.format_name,
                details={"missing": "<html>"}
            )

        # Check for head tag
        if not re.search(r'<head', content, re.IGNORECASE):
            self.logger.warning("Missing <head> tag")

        # Check for body tag
        if not re.search(r'<body', content, re.IGNORECASE):
            raise ValidationError(
                "Missing <body> tag",
                format_type=self.format_name,
                details={"missing": "<body>"}
            )

        # Check for closing tags
        if not re.search(r'</html>', content, re.IGNORECASE):
            raise ValidationError(
                "Missing </html> closing tag",
                format_type=self.format_name,
                details={"missing": "</html>"}
            )

        # Check for balanced tags (basic check)
        self._check_balanced_tags(content)

    def _check_balanced_tags(self, content: str) -> None:
        """
        Perform basic check for balanced HTML tags.

        Args:
            content: HTML content to check
        """
        # This is a very basic check - in production you'd want a proper HTML parser
        open_tags = re.findall(r'<([a-zA-Z][a-zA-Z0-9]*)(?:\s[^>]*)?>', content)
        close_tags = re.findall(r'</([a-zA-Z][a-zA-Z0-9]*)>', content)

        # Remove self-closing tags from open tags
        self_closing = {'br', 'img', 'input', 'meta', 'link', 'hr', 'source', 'embed'}
        open_tags = [tag for tag in open_tags if tag.lower() not in self_closing]

        # Basic balance check (this is not perfect but catches obvious issues)
        open_count = {}
        close_count = {}

        for tag in open_tags:
            tag_lower = tag.lower()
            open_count[tag_lower] = open_count.get(tag_lower, 0) + 1

        for tag in close_tags:
            tag_lower = tag.lower()
            close_count[tag_lower] = close_count.get(tag_lower, 0) + 1

        # Check for obvious imbalances
        for tag in set(open_count.keys()) | set(close_count.keys()):
            if open_count.get(tag, 0) != close_count.get(tag, 0):
                self.logger.warning(f"Potentially unbalanced tag: <{tag}>")
