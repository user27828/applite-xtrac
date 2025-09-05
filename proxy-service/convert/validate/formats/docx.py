"""
DOCX file validation.

Validates Microsoft Word DOCX files using ZIP structure and content checks.
"""

import zipfile
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def validate_docx(file_path: str) -> bool:
    """
    Validate DOCX file.

    Checks:
    - File is valid ZIP archive
    - Contains required DOCX structure ([Content_Types].xml, _rels/.rels, word/document.xml)
    - Has document content

    Args:
        file_path: Path to the DOCX file

    Returns:
        bool: True if validation passes

    Raises:
        ValueError: If validation fails
    """
    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            # Check for required DOCX files
            required_files = [
                '[Content_Types].xml',
                '_rels/.rels',
                'word/document.xml'
            ]

            for required_file in required_files:
                if required_file not in zf.namelist():
                    raise ValueError(f"Missing required DOCX file: {required_file}")

            # Check document content exists and has size
            try:
                doc_info = zf.getinfo('word/document.xml')
                if doc_info.file_size == 0:
                    raise ValueError("DOCX document content is empty")
            except KeyError:
                raise ValueError("word/document.xml not found in DOCX structure")

            # Optional: Check for core properties
            core_props_files = ['docProps/core.xml', 'docProps/app.xml']
            has_props = any(props_file in zf.namelist() for props_file in core_props_files)
            if not has_props:
                logger.warning("DOCX file missing standard properties")

            return True

    except zipfile.BadZipFile:
        raise ValueError("File is not a valid ZIP archive (required for DOCX)")
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Failed to validate DOCX: {e}")
