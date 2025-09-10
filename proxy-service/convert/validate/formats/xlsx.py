"""
XLSX file validation.

Validates Excel XLSX files using openpyxl for structure and content checks.
"""

from pathlib import Path
from typing import Optional
import logging

from ..base_validator import ArchiveBasedValidator, ValidationError

logger = logging.getLogger(__name__)


class XLSXValidator(ArchiveBasedValidator):
    """XLSX file validator using the base validation framework."""

    def __init__(self):
        # Define required files for XLSX format
        required_files = [
            '[Content_Types].xml',
            '_rels/.rels',
            'xl/workbook.xml'
        ]
        super().__init__("xlsx", required_files)

    def _validate_content(self, content: bytes, **options) -> bool:
        """
        Validate XLSX file content.

        Args:
            content: XLSX file content as bytes
            **options: Additional validation options

        Returns:
            bool: True if validation passes

        Raises:
            ValidationError: If validation fails
        """
        # Perform basic archive validation
        self._validate_basic_archive_content(content)

        # Validate XLSX-specific structure
        self._validate_xlsx_structure(content)

        return True

    def _validate_xlsx_structure(self, content: bytes) -> None:
        """
        Validate XLSX file structure.

        Args:
            content: XLSX file content as bytes

        Raises:
            ValidationError: If structure validation fails
        """
        # Check for required XLSX files
        required_files = [
            'xl/workbook.xml',
            'xl/worksheets/sheet1.xml',
            '[Content_Types].xml'
        ]

        missing_files = []
        for required_file in required_files:
            if not self._file_exists_in_archive(content, required_file):
                missing_files.append(required_file)

        if missing_files:
            raise ValidationError(
                f"Missing required XLSX files: {', '.join(missing_files)}",
                format_type=self.format_name,
                details={"missing_files": missing_files}
            )

        # Check for workbook relationships
        if not self._file_exists_in_archive(content, 'xl/_rels/workbook.xml.rels'):
            self.logger.warning("Missing workbook relationships file")

        # Validate content types
        content_types_content = self._extract_file_from_archive(content, '[Content_Types].xml')
        if content_types_content:
            self._validate_content_types(content_types_content.decode('utf-8'))

    def _validate_content_types(self, content_types_xml: str) -> None:
        """
        Validate Content_Types.xml content.

        Args:
            content_types_xml: Content of [Content_Types].xml
        """
        # Check for required content type declarations
        required_types = [
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'
        ]

        for content_type in required_types:
            if content_type not in content_types_xml:
                self.logger.warning(f"Missing content type declaration: {content_type}")