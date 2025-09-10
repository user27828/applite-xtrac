"""
File validation module for document conversion.

This module provides robust file type validation for various document formats,
ensuring files are valid before processing through the conversion pipeline.
"""

import os
import logging
from typing import Dict, Any, Optional, Union
from pathlib import Path

from .base_validator import ValidationError, create_validator_for_format

logger = logging.getLogger(__name__)


class FileValidator:
    """Factory class for file validation."""

    def __init__(self):
        self._validators = {}
        self._load_validators()

    def _load_validators(self):
        """Load all available format validators."""
        # Import validator classes
        from .formats import (
            html, pdf, docx, md, txt, json, tex,
            xlsx, pptx, odt, ods, odp
        )

        # Map format names to validator classes
        self._validator_classes = {
            'html': html.HTMLValidator,
            'pdf': pdf.PDFValidator,
            'docx': docx.DOCXValidator,
            'pptx': pptx.PPTXValidator,
            'md': md.MarkdownValidator,
            'txt': txt.TextValidator,
            'json': json.JSONValidator,
            'tex': tex.TeXValidator,
            'xlsx': xlsx.XLSXValidator,
            'odt': odt.ODTValidator,
            'ods': ods.ODSValidator,
            'odp': odp.ODPValidator,
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
            expected_format: Expected file format (html, pdf, docx, pptx, md, txt, json, tex, xlsx, odt, ods, odp)
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

        # Get validator class
        validator_class = self._validator_classes.get(expected_format.lower())
        if not validator_class:
            raise ValueError(f"Unsupported format: {expected_format}")

        try:
            # Create validator instance and validate
            validator = validator_class()
            return validator.validate_file(str(file_path), **options)
        except ValidationError:
            # Re-raise ValidationError as-is
            raise
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
) -> Optional[bool]:
    """
    Convenience function to validate a file.

    Args:
        file_path: Path to the file to validate
        expected_format: Expected file format
        **options: Additional validation options

    Returns:
        Optional[bool]: True if validation passes, None if content doesn't match format

    Raises:
        ValidationError: If validation fails
    """
    return get_validator().validate_file(file_path, expected_format, **options)
