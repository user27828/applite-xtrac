"""
XLSX file validation.

Validates Microsoft Excel XLSX files using ZIP structure and content checks.
"""

import zipfile
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def validate_xlsx(file_path: str) -> bool:
    """
    Validate XLSX file.

    Checks:
    - File is valid ZIP archive
    - Contains required XLSX structure ([Content_Types].xml, xl/workbook.xml)
    - Has workbook content

    Args:
        file_path: Path to the XLSX file

    Returns:
        bool: True if validation passes

    Raises:
        ValueError: If validation fails
    """
    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            # Check for required XLSX files
            required_files = [
                '[Content_Types].xml',
                'xl/workbook.xml'
            ]

            for required_file in required_files:
                if required_file not in zf.namelist():
                    raise ValueError(f"Missing required XLSX file: {required_file}")

            # Check workbook content exists and has size
            try:
                workbook_info = zf.getinfo('xl/workbook.xml')
                if workbook_info.file_size == 0:
                    raise ValueError("XLSX workbook content is empty")
            except KeyError:
                raise ValueError("xl/workbook.xml not found in XLSX structure")

            # Optional: Check for worksheets
            worksheets = [name for name in zf.namelist() if name.startswith('xl/worksheets/') and name.endswith('.xml')]
            if not worksheets:
                logger.warning("XLSX file contains no worksheets")

            # Optional: Check for shared strings
            shared_strings_files = [name for name in zf.namelist() if 'sharedStrings' in name]
            if not shared_strings_files:
                logger.info("XLSX file has no shared strings (may be expected for simple files)")

            return True

    except zipfile.BadZipFile:
        raise ValueError("File is not a valid ZIP archive (required for XLSX)")
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Failed to validate XLSX: {e}")
