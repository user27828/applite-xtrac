"""
Markdown file validation.

Validates Markdown files using structure and content checks.
"""

import re
from pathlib import Path
from typing import Optional
import logging

from ..base_validator import TextBasedValidator, ValidationError

logger = logging.getLogger(__name__)


class MarkdownValidator(TextBasedValidator):
    """Markdown file validator using the base validation framework."""

    def __init__(self):
        super().__init__("md")

    def _validate_content(self, content: str, **options) -> bool:
        """
        Validate Markdown file content.

        Args:
            content: Markdown content to validate
            **options: Additional validation options

        Returns:
            bool: True if validation passes

        Raises:
            ValidationError: If validation fails
        """
        # Perform basic text content validation
        self._validate_basic_text_content(content)

        # Validate Markdown-specific structure
        self._validate_markdown_structure(content)

        return True

    def _validate_markdown_structure(self, content: str) -> None:
        """
        Validate Markdown document structure.

        Args:
            content: Markdown content to validate

        Raises:
            ValidationError: If structure validation fails
        """
        lines = content.split('\n')

        # Check for basic content
        if not any(line.strip() for line in lines):
            raise ValidationError(
                "Markdown file appears to be empty",
                format_type=self.format_name,
                details={"total_lines": len(lines), "empty_lines": sum(1 for line in lines if not line.strip())}
            )

        # Check for common Markdown elements (optional - just warnings)
        has_headers = any(re.match(r'^#{1,6}\s', line) for line in lines)
        has_links = any('[' in line and '](' in line for line in lines)
        has_lists = any(re.match(r'^[\s]*[-\*\+]|\d+\.', line) for line in lines)

        if not has_headers and not has_links and not has_lists:
            self.logger.info("Markdown file contains no common Markdown elements (headers, links, lists)")

        # Check for code blocks (basic validation)
        self._validate_code_blocks(content)

    def _validate_code_blocks(self, content: str) -> None:
        """
        Validate code blocks in Markdown.

        Args:
            content: Markdown content to validate
        """
        # Check for fenced code blocks
        fenced_blocks = re.findall(r'```[\s\S]*?```', content, re.MULTILINE)
        for i, block in enumerate(fenced_blocks):
            if not block.strip():
                self.logger.warning(f"Empty fenced code block found at position {i}")

        # Check for inline code
        inline_code = re.findall(r'`[^`\n]+`', content)
        if not inline_code and not fenced_blocks:
            self.logger.info("No code blocks found in Markdown file")
