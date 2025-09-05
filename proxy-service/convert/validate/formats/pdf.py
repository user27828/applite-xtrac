"""
PDF file validation.

Validates PDF files using magic bytes and basic structure checks.
"""

import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def validate_pdf(file_path: str) -> bool:
    """
    Validate PDF file.

    Checks:
    - File starts with PDF magic bytes (%PDF-)
    - Contains EOF marker
    - Basic structure validation

    Args:
        file_path: Path to the PDF file

    Returns:
        bool: True if validation passes

    Raises:
        ValueError: If validation fails
    """
    try:
        with open(file_path, 'rb') as f:
            # Read first 1024 bytes for header check
            header = f.read(1024)

            # Check PDF magic bytes
            if not header.startswith(b'%PDF-'):
                raise ValueError("File does not have valid PDF header")

            # Check version (should be 1.x)
            try:
                version_part = header[5:8].decode('ascii')
                major_version = int(version_part[0])
                if major_version < 1:
                    raise ValueError(f"Unsupported PDF version: {version_part}")
            except (ValueError, IndexError):
                raise ValueError("Invalid PDF version format")

            # Read last 1024 bytes for EOF check
            f.seek(-min(1024, os.path.getsize(file_path)), 2)
            footer = f.read()

            # Check for EOF marker
            if b'%%EOF' not in footer:
                raise ValueError("PDF file missing EOF marker")

            return True

    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Failed to validate PDF: {e}")
