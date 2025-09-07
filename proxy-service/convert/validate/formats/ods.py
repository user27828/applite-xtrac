"""
ODS file validation.

Validates OpenDocument Spreadsheet (ODS) files using ZIP structure and content checks.
"""

import zipfile
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def validate_ods(file_path: str) -> bool:
    """
    Validate ODS file.

    Checks:
    - File is valid ZIP archive
    - Contains required ODS structure (mimetype, META-INF/manifest.xml, content.xml)
    - Has spreadsheet content

    Args:
        file_path: Path to the ODS file

    Returns:
        bool: True if validation passes

    Raises:
        ValueError: If validation fails
    """
    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            # Check for required ODS files
            required_files = [
                'mimetype',
                'META-INF/manifest.xml',
                'content.xml'
            ]

            for required_file in required_files:
                if required_file not in zf.namelist():
                    raise ValueError(f"Missing required ODS file: {required_file}")

            # Check mimetype content
            try:
                with zf.open('mimetype') as f:
                    mimetype_content = f.read().decode('utf-8').strip()
                    if mimetype_content != 'application/vnd.oasis.opendocument.spreadsheet':
                        raise ValueError(f"Invalid ODS mimetype: {mimetype_content}")
            except KeyError:
                raise ValueError("mimetype file not found in ODS structure")

            # Check document content exists and has size
            try:
                content_info = zf.getinfo('content.xml')
                if content_info.file_size == 0:
                    raise ValueError("ODS spreadsheet content is empty")
            except KeyError:
                raise ValueError("content.xml not found in ODS structure")

            # Optional: Check for styles.xml (spreadsheet styling)
            if 'styles.xml' in zf.namelist():
                try:
                    styles_info = zf.getinfo('styles.xml')
                    if styles_info.file_size == 0:
                        logger.warning("ODS file has empty styles")
                except KeyError:
                    pass  # styles.xml is optional

            return True

    except zipfile.BadZipFile:
        raise ValueError("File is not a valid ZIP archive (required for ODS)")
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Failed to validate ODS: {e}")
