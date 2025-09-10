"""
ODT file validation.

Validates OpenDocument Text files using structure and content checks.
"""

from pathlib import Path
from typing import Optional
import logging

from ..base_validator import ArchiveBasedValidator, ValidationError

logger = logging.getLogger(__name__)


class ODTValidator(ArchiveBasedValidator):
    """ODT file validator using the base validation framework."""

    def __init__(self):
        # Define required files for ODT format
        required_files = [
            'mimetype',
            'META-INF/manifest.xml',
            'content.xml'
        ]
        super().__init__("odt", required_files)

    def _validate_content(self, content: bytes, **options) -> bool:
        """
        Validate ODT file content.

        Args:
            content: ODT file content as bytes
            **options: Additional validation options

        Returns:
            bool: True if validation passes

        Raises:
            ValidationError: If validation fails
        """
        # Perform basic archive validation
        self._validate_basic_archive_content(content)

        # Validate ODT-specific structure
        self._validate_odt_structure(content)

        return True

    def _validate_odt_structure(self, content: bytes) -> None:
        """
        Validate ODT file structure.

        Args:
            content: ODT file content as bytes

        Raises:
            ValidationError: If structure validation fails
        """
        # Check for required ODT files
        required_files = [
            'content.xml',
            'styles.xml',
            'meta.xml',
            'META-INF/manifest.xml'
        ]

        missing_files = []
        for required_file in required_files:
            if not self._file_exists_in_archive(content, required_file):
                missing_files.append(required_file)

        if missing_files:
            raise ValidationError(
                f"Missing required ODT files: {', '.join(missing_files)}",
                format_type=self.format_name,
                details={"missing_files": missing_files}
            )

        # Validate manifest
        manifest_content = self._extract_file_from_archive(content, 'META-INF/manifest.xml')
        if manifest_content:
            self._validate_manifest(manifest_content.decode('utf-8'))

        # Validate content.xml structure
        content_xml = self._extract_file_from_archive(content, 'content.xml')
        if content_xml:
            self._validate_content_xml(content_xml.decode('utf-8'))

    def _validate_manifest(self, manifest_xml: str) -> None:
        """
        Validate manifest.xml content.

        Args:
            manifest_xml: Content of manifest.xml
        """
        # Check for required manifest entries
        required_entries = [
            'content.xml',
            'styles.xml',
            'meta.xml'
        ]

        for entry in required_entries:
            if f'<manifest:file-entry manifest:full-path="{entry}"' not in manifest_xml:
                self.logger.warning(f"Missing manifest entry for: {entry}")

    def _validate_content_xml(self, content_xml: str) -> None:
        """
        Validate content.xml structure.

        Args:
            content_xml: Content of content.xml
        """
        # Check for basic ODT structure
        if '<office:document-content' not in content_xml:
            raise ValidationError(
                "Invalid ODT content.xml: missing document-content element",
                format_type=self.format_name,
                details={"missing": "office:document-content"}
            )

        if '<office:body>' not in content_xml:
            raise ValidationError(
                "Invalid ODT content.xml: missing body element",
                format_type=self.format_name,
                details={"missing": "office:body"}
            )

        # Check for text content
        if '<office:text>' not in content_xml:
            self.logger.warning("ODT file contains no text content")