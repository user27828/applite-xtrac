"""
Text file validation.

Validates plain text files using encoding checks.
"""

from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def validate_text(file_path: str) -> bool:
    """
    Validate plain text file.

    Checks:
    - File can be read as UTF-8 text
    - Contains some content

    Args:
        file_path: Path to the text file

    Returns:
        bool: True if validation passes

    Raises:
        ValueError: If validation fails
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='strict') as f:
            content = f.read()
    except UnicodeDecodeError:
        raise ValueError("Text file must be valid UTF-8 encoded text")
    except Exception as e:
        raise ValueError(f"Failed to read text file: {e}")

    if not content.strip():
        raise ValueError("Text file is empty")

    # Additional check: ensure no binary content (null bytes)
    if '\x00' in content:
        raise ValueError("Text file contains binary data (null bytes)")

    return True
