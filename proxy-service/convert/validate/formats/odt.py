"""
ODT file validation.

Validates OpenDocument Text (ODT) files using ZIP structure and content checks.
"""

import zipfile
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def validate_odt(file_path: str) -> bool:
    """
    Validate ODT file.

    Checks:
    - File is valid ZIP archive
    - Contains required ODT structure (mimetype, META-INF/manifest.xml, content.xml)
    - Has document content

    Args:
        file_path: Path to the ODT file

    Returns:
        bool: True if validation passes

    Raises:
        ValueError: If validation fails
    """
    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            # Check for required ODT files
            required_files = [
                'mimetype',
                'META-INF/manifest.xml',
                'content.xml'
            ]

            for required_file in required_files:
                if required_file not in zf.namelist():
                    raise ValueError(f"Missing required ODT file: {required_file}")

            # Check mimetype content
            try:
                with zf.open('mimetype') as f:
                    mimetype_content = f.read().decode('utf-8').strip()
                    if mimetype_content != 'application/vnd.oasis.opendocument.text':
                        raise ValueError(f"Invalid ODT mimetype: {mimetype_content}")
            except KeyError:
                raise ValueError("mimetype file not found in ODT structure")

            # Check document content exists and has size
            try:
                content_info = zf.getinfo('content.xml')
                if content_info.file_size == 0:
                    raise ValueError("ODT document content is empty")
            except KeyError:
                raise ValueError("content.xml not found in ODT structure")

            # Optional: Check for meta.xml (document metadata)
            if 'meta.xml' in zf.namelist():
                try:
                    meta_info = zf.getinfo('meta.xml')
                    if meta_info.file_size == 0:
                        logger.warning("ODT file has empty metadata")
                except KeyError:
                    pass  # meta.xml is optional

            return True

    except zipfile.BadZipFile:
        raise ValueError("File is not a valid ZIP archive (required for ODT)")
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Failed to validate ODT: {e}")
