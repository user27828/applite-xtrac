"""
PPTX file validation.

Validates Microsoft PowerPoint PPTX files using ZIP structure and content checks.
"""

import zipfile
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def validate_pptx(file_path: str) -> bool:
    """
    Validate PPTX file.

    Checks:
    - File is valid ZIP archive
    - Contains required PPTX structure ([Content_Types].xml, _rels/.rels, ppt/presentation.xml)
    - Has presentation content

    Args:
        file_path: Path to the PPTX file

    Returns:
        bool: True if validation passes

    Raises:
        ValueError: If validation fails
    """
    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            # Check for required PPTX files
            required_files = [
                '[Content_Types].xml',
                '_rels/.rels',
                'ppt/presentation.xml'
            ]

            for required_file in required_files:
                if required_file not in zf.namelist():
                    raise ValueError(f"Missing required PPTX file: {required_file}")

            # Check presentation content exists and has size
            try:
                pres_info = zf.getinfo('ppt/presentation.xml')
                if pres_info.file_size == 0:
                    raise ValueError("PPTX presentation content is empty")
            except KeyError:
                raise ValueError("PPTX presentation.xml not found")

            # Additional validation: check for slides
            slide_count = 0
            for name in zf.namelist():
                if name.startswith('ppt/slides/slide') and name.endswith('.xml'):
                    slide_count += 1

            if slide_count == 0:
                logger.warning(f"PPTX file has no slides: {file_path}")

            return True

    except zipfile.BadZipFile:
        raise ValueError("File is not a valid ZIP archive (not a PPTX file)")
    except Exception as e:
        logger.error(f"PPTX validation error for {file_path}: {e}")
        raise ValueError(f"PPTX validation failed: {str(e)}")
