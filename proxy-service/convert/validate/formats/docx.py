"""
DOCX file validation.

Validates Microsoft Word DOCX files using ZIP structure and content checks.
"""

import zipfile
from pathlib import Path
from typing import Optional
import logging

from ..base_validator import ArchiveBasedValidator, ValidationError

logger = logging.getLogger(__name__)


class DOCXValidator(ArchiveBasedValidator):
    """DOCX file validator using the base validation framework."""

    def __init__(self):
        # Define required files for DOCX format
        required_files = [
            '[Content_Types].xml',
            '_rels/.rels',
            'word/document.xml'
        ]
        super().__init__("docx", required_files)

    def _validate_content(self, content: bytes, **options) -> bool:
        """
        Validate DOCX file content.

        Args:
            content: DOCX file content as bytes
            **options: Additional validation options

        Returns:
            bool: True if validation passes

        Raises:
            ValidationError: If validation fails
        """
        # Perform basic archive validation
        self._validate_basic_archive_content(content)

        # Validate DOCX-specific structure
        self._validate_docx_structure(content)

        return True

    def _validate_basic_archive_content(self, content: bytes) -> None:
        """Validate DOCX archive content directly from bytes."""
        import io

        try:
            with zipfile.ZipFile(io.BytesIO(content), 'r') as zf:
                # Check for required DOCX files
                namelist = zf.namelist()
                missing_files = []

                for required_file in self.required_files:
                    if required_file not in namelist:
                        missing_files.append(required_file)

                if missing_files:
                    raise ValidationError(
                        f"Missing required DOCX files: {missing_files}",
                        format_type=self.format_name,
                        details={
                            "missing_files": missing_files,
                            "available_files": namelist[:10]  # Limit for readability
                        }
                    )

                # Check document content exists and has size
                try:
                    doc_info = zf.getinfo('word/document.xml')
                    if doc_info.file_size == 0:
                        raise ValidationError(
                            "DOCX document content is empty",
                            format_type=self.format_name,
                            details={"document_size": doc_info.file_size}
                        )
                except KeyError:
                    raise ValidationError(
                        "DOCX document.xml not found in archive",
                        format_type=self.format_name
                    )

        except zipfile.BadZipFile as e:
            raise ValidationError(
                f"Invalid DOCX file (not a valid ZIP archive): {e}",
                format_type=self.format_name,
                details={"zip_error": str(e)}
            )
        except Exception as e:
            raise ValidationError(
                f"Failed to validate DOCX structure: {e}",
                format_type=self.format_name,
                details={"validation_error": str(e)}
            )

    def _validate_docx_structure(self, content: bytes) -> None:
        """
        Validate DOCX file structure.

        Args:
            content: DOCX file content as bytes

        Raises:
            ValidationError: If structure validation fails
        """
        # Additional DOCX-specific validation can be added here
        # For now, the basic archive validation covers the main requirements
        pass
