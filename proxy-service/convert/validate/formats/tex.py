"""
TeX file validation.

Validates TeX/LaTeX files using syntax and structure checks.
"""

import re
from pathlib import Path
from typing import Optional
import logging

from ..base_validator import TextBasedValidator, ValidationError

logger = logging.getLogger(__name__)


class TeXValidator(TextBasedValidator):
    """TeX/LaTeX file validator using the base validation framework."""

    def __init__(self):
        super().__init__("tex")

    def _validate_content(self, content: str, **options) -> Optional[bool]:
        """
        Validate TeX file content.

        Args:
            content: TeX content to validate
            **options: Additional validation options

        Returns:
            Optional[bool]: True if valid TeX, None if plain text content

        Raises:
            ValidationError: If validation fails for actual TeX content
        """
        # Perform basic text content validation
        self._validate_basic_text_content(content)

        # Validate TeX-specific structure
        tex_validation_result = self._validate_tex_structure(content)
        
        # Return None if content is plain text (not TeX)
        if tex_validation_result is None:
            return None

        return True

    def _validate_tex_structure(self, content: str) -> Optional[bool]:
        """
        Validate TeX document structure.

        Args:
            content: TeX content to validate

        Returns:
            Optional[bool]: True if valid TeX, None if plain text (not TeX), raises ValidationError for invalid TeX

        Raises:
            ValidationError: If structure validation fails for actual TeX content
        """
        # For generated TeX files, be more lenient
        # Check if it has at least some TeX-like content (backslash commands or braces)
        has_tex_commands = bool(re.search(r'\\[a-zA-Z]', content))
        has_tex_formatting = bool(re.search(r'\{[^}]*\}', content))
        
        if not (has_tex_commands or has_tex_formatting):
            # Return None for plain text content - not an error, just not TeX
            return None

        # Check for document class (optional for fragments)
        has_document_class = bool(re.search(r'\\documentclass', content))
        has_document_env = bool(re.search(r'\\begin\{document\}', content) and re.search(r'\\end\{document\}', content))

        if has_document_class and not has_document_env:
            self.logger.warning("Found \\documentclass but missing document environment")
        elif has_document_env and not has_document_class:
            self.logger.warning("Found document environment but missing \\documentclass")

        # Check for balanced braces (basic check)
        brace_count = content.count('{') - content.count('}')
        if brace_count != 0:
            raise ValidationError(
                f"Unbalanced braces: {brace_count} unmatched",
                format_type=self.format_name,
                details={"brace_imbalance": brace_count}
            )

        # Check for common LaTeX syntax issues (warnings only for generated content)
        self._check_latex_syntax(content)

        return True

    def _check_latex_syntax(self, content: str) -> None:
        """
        Check for common LaTeX syntax issues.

        Args:
            content: TeX content to check
        """
        # Check for unescaped special characters in text
        # This is a basic check - LaTeX has many special characters
        special_chars = ['&', '%', '$', '#', '_', '^', '~']
        for char in special_chars:
            # Look for unescaped special characters (not preceded by \)
            pattern = rf'(?<!\\){re.escape(char)}'
            if re.search(pattern, content):
                self.logger.warning(f"Found unescaped special character '{char}' - may need escaping")

        # Check for common command issues
        if re.search(r'\\[a-zA-Z]+\s*\{[^}]*$', content, re.MULTILINE):
            self.logger.warning("Found incomplete LaTeX command with unclosed brace")