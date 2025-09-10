"""
Text file validation.

Validates plain text files using encoding and content checks.
"""

from pathlib import Path
from typing import Optional
import logging

from ..base_validator import TextBasedValidator, ValidationError

logger = logging.getLogger(__name__)


class TextValidator(TextBasedValidator):
    """Text file validator using the base validation framework."""

    def __init__(self):
        super().__init__("txt")

    def _validate_content(self, content: str, **options) -> bool:
        """
        Validate text file content.

        Args:
            content: Text content to validate
            **options: Additional validation options

        Returns:
            bool: True if validation passes

        Raises:
            ValidationError: If validation fails
        """
        # Perform basic text content validation
        self._validate_basic_text_content(content)

        # Additional text-specific validation
        self._validate_text_specific_content(content)

        return True

    def _validate_text_specific_content(self, content: str) -> None:
        """
        Validate text-specific content requirements.

        Args:
            content: Text content to validate
        """
        # Check for minimum content length
        if len(content.strip()) == 0:
            raise ValidationError(
                "Text file is empty or contains only whitespace",
                format_type=self.format_name,
                details={"content_length": len(content), "stripped_length": len(content.strip())}
            )

        # Check for reasonable line lengths (optional warning)
        lines = content.split('\n')
        long_lines = [i for i, line in enumerate(lines) if len(line) > 1000]
        if long_lines:
            self.logger.warning(f"Found {len(long_lines)} lines longer than 1000 characters")

        # Check for binary content mixed with text (basic check)
        if '\x00' in content:
            raise ValidationError(
                "Text file contains null bytes (possible binary content)",
                format_type=self.format_name,
                details={"null_bytes_found": content.count('\x00')}
            )
