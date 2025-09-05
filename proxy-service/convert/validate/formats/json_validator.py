"""
JSON file validation.

Validates JSON files using parsing and structure checks.
"""

import json
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def validate_json(file_path: str) -> bool:
    """
    Validate JSON file.

    Checks:
    - File is valid JSON
    - Contains some content
    - Basic structure validation

    Args:
        file_path: Path to the JSON file

    Returns:
        bool: True if validation passes

    Raises:
        ValueError: If validation fails
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='strict') as f:
            content = f.read()
    except UnicodeDecodeError:
        raise ValueError("JSON file must be valid UTF-8 encoded text")
    except Exception as e:
        raise ValueError(f"Failed to read JSON file: {e}")

    if not content.strip():
        raise ValueError("JSON file is empty")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")

    # Additional validation: check if it's not just a primitive
    if not isinstance(parsed, (dict, list)):
        logger.warning("JSON file contains only a primitive value (not object or array)")

    return True
