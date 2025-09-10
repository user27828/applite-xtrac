"""
Base file validator classes for document format validation.

This module provides base classes and utilities for file validation,
reducing code duplication across format-specific validators.
"""

import os
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Union, Any, Dict
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationResult(Enum):
    """Result of file validation."""
    VALID = "valid"
    INVALID = "invalid"
    ERROR = "error"


class ValidationError(Exception):
    """Raised when file validation fails."""
    def __init__(self, message: str, format_type: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.format_type = format_type
        self.details = details or {}


class BaseFileValidator(ABC):
    """
    Base class for file format validators.

    Provides common functionality for file reading, error handling, and validation
    patterns that can be inherited by specific format validators.
    """

    def __init__(self, format_name: str):
        self.format_name = format_name
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate_file(
        self,
        file_path: Union[str, Path],
        **options
    ) -> Optional[bool]:
        """
        Main validation method that handles common file operations.

        Args:
            file_path: Path to the file to validate
            **options: Format-specific validation options

        Returns:
            Optional[bool]: True if validation passes, None if content doesn't match format

        Raises:
            ValidationError: If validation fails
        """
        file_path = Path(file_path)

        # Basic file checks
        self._check_file_exists(file_path)
        self._check_file_size(file_path)

        # Read file content
        content = self._read_file_content(file_path)

        # Perform format-specific validation
        return self._validate_content(content, **options)

    def _check_file_exists(self, file_path: Path) -> None:
        """Check if file exists."""
        if not file_path.exists():
            raise ValidationError(
                f"File does not exist: {file_path}",
                format_type=self.format_name
            )

    def _check_file_size(self, file_path: Path) -> None:
        """Check if file has content (non-zero size)."""
        file_size = file_path.stat().st_size
        if file_size == 0:
            raise ValidationError(
                "File is empty (size 0)",
                format_type=self.format_name,
                details={"file_size": file_size}
            )

    def _read_file_content(self, file_path: Path) -> Union[str, bytes]:
        """
        Read file content with appropriate encoding.

        This method can be overridden by subclasses for specific reading requirements.

        Args:
            file_path: Path to the file

        Returns:
            File content as string or bytes

        Raises:
            ValidationError: If file cannot be read
        """
        try:
            # Default to text reading - subclasses can override for binary files
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except UnicodeDecodeError as e:
            raise ValidationError(
                f"File encoding error: {e}",
                format_type=self.format_name,
                details={"encoding_error": str(e)}
            )
        except Exception as e:
            raise ValidationError(
                f"Failed to read file: {e}",
                format_type=self.format_name,
                details={"read_error": str(e)}
            )

    @abstractmethod
    def _validate_content(self, content: Union[str, bytes], **options) -> Optional[bool]:
        """
        Perform format-specific content validation.

        This method must be implemented by subclasses.

        Args:
            content: File content to validate
            **options: Format-specific validation options

        Returns:
            Optional[bool]: True if validation passes, None if content doesn't match format (not an error)

        Raises:
            ValidationError: If validation fails for actual format content
        """
        pass


class TextBasedValidator(BaseFileValidator):
    """
    Base class for text-based file validators.

    Provides common functionality for text file validation including encoding checks
    and basic content validation.
    """

    def __init__(self, format_name: str):
        super().__init__(format_name)

    def _read_file_content(self, file_path: Path) -> str:
        """Read text file content with strict UTF-8 validation."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='strict') as f:
                return f.read()
        except UnicodeDecodeError as e:
            raise ValidationError(
                f"File must be valid UTF-8 encoded text: {e}",
                format_type=self.format_name,
                details={"encoding_error": str(e)}
            )
        except Exception as e:
            raise ValidationError(
                f"Failed to read text file: {e}",
                format_type=self.format_name,
                details={"read_error": str(e)}
            )

    def _validate_basic_text_content(self, content: str) -> None:
        """Perform basic text content validation."""
        if not content.strip():
            raise ValidationError(
                "File is empty or contains only whitespace",
                format_type=self.format_name,
                details={"content_length": len(content)}
            )

        # Check for binary content (null bytes)
        if '\x00' in content:
            raise ValidationError(
                "File contains binary data (null bytes)",
                format_type=self.format_name
            )


class BinaryBasedValidator(BaseFileValidator):
    """
    Base class for binary file validators.

    Provides common functionality for binary file validation.
    """

    def __init__(self, format_name: str):
        super().__init__(format_name)

    def _read_file_content(self, file_path: Path) -> bytes:
        """Read binary file content."""
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            raise ValidationError(
                f"Failed to read binary file: {e}",
                format_type=self.format_name,
                details={"read_error": str(e)}
            )

    def _validate_basic_binary_content(self, content: bytes) -> None:
        """Perform basic binary content validation."""
        if len(content) == 0:
            raise ValidationError(
                "File is empty",
                format_type=self.format_name,
                details={"content_length": len(content)}
            )

        # Check for reasonable file size (basic sanity check)
        if len(content) > 100 * 1024 * 1024:  # 100MB limit
            raise ValidationError(
                "File is too large for validation",
                format_type=self.format_name,
                details={"content_length": len(content)}
            )


class ArchiveBasedValidator(BinaryBasedValidator):
    """
    Base class for archive-based file validators (ZIP, etc.).

    Provides common functionality for validating archive file structures.
    """

    def __init__(self, format_name: str, required_files: list):
        super().__init__(format_name)
        self.required_files = required_files

    def _validate_basic_archive_content(self, content: bytes) -> None:
        """Validate basic archive structure from bytes content."""
        import io
        import zipfile

        try:
            with zipfile.ZipFile(io.BytesIO(content), 'r') as zf:
                # Check for required files
                namelist = zf.namelist()
                missing_files = []

                for required_file in self.required_files:
                    if required_file not in namelist:
                        missing_files.append(required_file)

                if missing_files:
                    raise ValidationError(
                        f"Missing required files: {missing_files}",
                        format_type=self.format_name,
                        details={
                            "missing_files": missing_files,
                            "available_files": namelist[:10]  # Limit for readability
                        }
                    )

        except zipfile.BadZipFile as e:
            raise ValidationError(
                f"Invalid archive file: {e}",
                format_type=self.format_name,
                details={"archive_error": str(e)}
            )
        except Exception as e:
            raise ValidationError(
                f"Failed to validate archive structure: {e}",
                format_type=self.format_name,
                details={"validation_error": str(e)}
            )

    def _file_exists_in_archive(self, content: bytes, filename: str) -> bool:
        """Check if a file exists in the archive."""
        import io
        import zipfile

        try:
            with zipfile.ZipFile(io.BytesIO(content), 'r') as zf:
                return filename in zf.namelist()
        except Exception:
            return False

    def _extract_file_from_archive(self, content: bytes, filename: str) -> Optional[bytes]:
        """Extract a file from the archive."""
        import io
        import zipfile

        try:
            with zipfile.ZipFile(io.BytesIO(content), 'r') as zf:
                if filename in zf.namelist():
                    return zf.read(filename)
        except Exception:
            pass
        return None

    def _validate_archive_structure(self, file_path: Path) -> None:
        """Validate archive file structure and required files."""
        import zipfile

        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                # Check for required files
                namelist = zf.namelist()
                missing_files = []

                for required_file in self.required_files:
                    if required_file not in namelist:
                        missing_files.append(required_file)

                if missing_files:
                    raise ValidationError(
                        f"Missing required files: {missing_files}",
                        format_type=self.format_name,
                        details={
                            "missing_files": missing_files,
                            "available_files": namelist[:10]  # Limit for readability
                        }
                    )

        except zipfile.BadZipFile as e:
            raise ValidationError(
                f"Invalid archive file: {e}",
                format_type=self.format_name,
                details={"archive_error": str(e)}
            )
        except Exception as e:
            raise ValidationError(
                f"Failed to validate archive structure: {e}",
                format_type=self.format_name,
                details={"validation_error": str(e)}
            )


def create_validator_for_format(format_name: str) -> BaseFileValidator:
    """
    Factory function to create appropriate validator for a format.

    Args:
        format_name: The format name (html, pdf, docx, etc.)

    Returns:
        Appropriate validator instance

    Raises:
        ValueError: If format is not supported
    """
    # Import here to avoid circular imports
    from .formats import (
        html, pdf, docx, md, txt, json, tex,
        xlsx, pptx, odt, ods, odp
    )

    format_validators = {
        'html': lambda: html.HTMLValidator(),
        'pdf': lambda: pdf.PDFValidator(),
        'docx': lambda: docx.DOCXValidator(),
        'pptx': lambda: pptx.PPTXValidator(),
        'md': lambda: md.MarkdownValidator(),
        'txt': lambda: txt.TextValidator(),
        'json': lambda: json.JSONValidator(),
        'tex': lambda: tex.TeXValidator(),
        'xlsx': lambda: xlsx.XLSXValidator(),
        'odt': lambda: odt.ODTValidator(),
        'ods': lambda: ods.ODSValidator(),
        'odp': lambda: odp.ODPValidator(),
    }

    validator_factory = format_validators.get(format_name.lower())
    if not validator_factory:
        raise ValueError(f"Unsupported format: {format_name}")

    return validator_factory()
