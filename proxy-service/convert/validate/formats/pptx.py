"""
PPTX file validation.

Validates PowerPoint PPTX files using structure and content checks.
"""

from pathlib import Path
from typing import Optional
import logging

from ..base_validator import ArchiveBasedValidator, ValidationError

logger = logging.getLogger(__name__)


class PPTXValidator(ArchiveBasedValidator):
    """PPTX file validator using the base validation framework."""

    def __init__(self):
        # Define required files for PPTX format
        required_files = [
            '[Content_Types].xml',
            '_rels/.rels',
            'ppt/presentation.xml'
        ]
        super().__init__("pptx", required_files)

    def _validate_content(self, content: bytes, **options) -> bool:
        """
        Validate PPTX file content.

        Args:
            content: PPTX file content as bytes
            **options: Additional validation options

        Returns:
            bool: True if validation passes

        Raises:
            ValidationError: If validation fails
        """
        # Perform basic archive validation
        self._validate_basic_archive_content(content)

        # Validate PPTX-specific structure
        self._validate_pptx_structure(content)

        return True

    def _validate_pptx_structure(self, content: bytes) -> None:
        """
        Validate PPTX file structure.

        Args:
            content: PPTX file content as bytes

        Raises:
            ValidationError: If structure validation fails
        """
        # Check for required PPTX files
        required_files = [
            'ppt/presentation.xml',
            '[Content_Types].xml'
        ]

        missing_files = []
        for required_file in required_files:
            if not self._file_exists_in_archive(content, required_file):
                missing_files.append(required_file)

        if missing_files:
            raise ValidationError(
                f"Missing required PPTX files: {', '.join(missing_files)}",
                format_type=self.format_name,
                details={"missing_files": missing_files}
            )

        # Check for presentation relationships
        if not self._file_exists_in_archive(content, 'ppt/_rels/presentation.xml.rels'):
            self.logger.warning("Missing presentation relationships file")

        # Validate content types
        content_types_content = self._extract_file_from_archive(content, '[Content_Types].xml')
        if content_types_content:
            self._validate_content_types(content_types_content.decode('utf-8'))

        # Check for slides
        self._validate_slides(content)

    def _validate_content_types(self, content_types_xml: str) -> None:
        """
        Validate Content_Types.xml content.

        Args:
            content_types_xml: Content of [Content_Types].xml
        """
        # Check for required content type declarations
        required_types = [
            'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml',
            'application/vnd.openxmlformats-officedocument.presentationml.slide+xml'
        ]

        for content_type in required_types:
            if content_type not in content_types_xml:
                self.logger.warning(f"Missing content type declaration: {content_type}")

    def _validate_slides(self, content: bytes) -> None:
        """
        Validate that the presentation has slides.

        Args:
            content: PPTX file content as bytes
        """
        # Check if there are any slide files
        slide_pattern = 'ppt/slides/slide'
        has_slides = False

        # This is a simplified check - in a real implementation,
        # you'd need to parse the presentation.xml to get slide count
        for i in range(1, 100):  # Check for first 99 slides
            slide_file = f"{slide_pattern}{i}.xml"
            if self._file_exists_in_archive(content, slide_file):
                has_slides = True
                break

        if not has_slides:
            self.logger.warning("No slides found in presentation")