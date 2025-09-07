"""
File validation module for document conversion.

This module provides robust file type validation for various document formats,
ensuring files are valid before processing through the conversion pipeline.
"""

import os
import logging
from typing import Dict, Any, Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Raised when file validation fails."""
    pass

class FileValidator:
    """Factory class for file validation."""

    def __init__(self):
        self._validators = {}
        self._load_validators()

    def _load_validators(self):
        """Load all available format validators."""
        from .formats import html, pdf, docx, md, txt, json_validator, tex, xlsx, pptx

        self._validators = {
            'html': html.validate_html,
            'pdf': pdf.validate_pdf,
            'docx': docx.validate_docx,
            'pptx': pptx.validate_pptx,
            'md': md.validate_markdown,
            'txt': txt.validate_text,
            'json': json_validator.validate_json,
            'tex': tex.validate_tex,
            'xlsx': xlsx.validate_xlsx,
        }

    def validate_file(
        self,
        file_path: Union[str, Path],
        expected_format: str,
        **options
    ) -> bool:
        """
        Validate a file against expected format.

        Args:
            file_path: Path to the file to validate
            expected_format: Expected file format (html, pdf, docx, md, txt, json, tex)
            **options: Additional validation options
                - full: bool (for HTML validation - whether to expect full document)

        Returns:
            bool: True if validation passes

        Raises:
            ValidationError: If validation fails
            ValueError: If format is not supported
        """
        file_path = Path(file_path)

        # Check if file exists
        if not file_path.exists():
            raise ValidationError(f"File does not exist: {file_path}")

        # Check file size
        file_size = file_path.stat().st_size
        if file_size == 0:
            raise ValidationError("File is empty (size 0)")

        # Get validator
        validator = self._validators.get(expected_format.lower())
        if not validator:
            raise ValueError(f"Unsupported format: {expected_format}")

        try:
            return validator(str(file_path), **options)
        except Exception as e:
            logger.error(f"Validation failed for {file_path}: {e}")
            raise ValidationError(f"Validation failed: {str(e)}")

# Global validator instance
_validator = None

def get_validator() -> FileValidator:
    """Get the global file validator instance."""
    global _validator
    if _validator is None:
        _validator = FileValidator()
    return _validator

def validate_file(
    file_path: Union[str, Path],
    expected_format: str,
    **options
) -> bool:
    """
    Convenience function to validate a file.

    Args:
        file_path: Path to the file to validate
        expected_format: Expected file format
        **options: Additional validation options

    Returns:
        bool: True if validation passes

    Raises:
        ValidationError: If validation fails
    """
    return get_validator().validate_file(file_path, expected_format, **options)
