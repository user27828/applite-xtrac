"""
Markdown file validation.

Validates Markdown files using encoding and basic content checks.
"""

from pathlib import Path
from typing import Optional
import logging
import re

logger = logging.getLogger(__name__)

def validate_markdown(file_path: str) -> bool:
    """
    Validate Markdown file.

    Checks:
    - File can be read as UTF-8 text
    - Contains some content
    - Basic Markdown structure (optional headers, lists, etc.)

    Args:
        file_path: Path to the Markdown file

    Returns:
        bool: True if validation passes

    Raises:
        ValueError: If validation fails
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='strict') as f:
            content = f.read()
    except UnicodeDecodeError:
        raise ValueError("Markdown file must be valid UTF-8 encoded text")
    except Exception as e:
        raise ValueError(f"Failed to read Markdown file: {e}")

    if not content.strip():
        raise ValueError("Markdown file is empty")

    # Basic Markdown validation - check for common patterns
    # This is permissive since Markdown can be plain text
    lines = content.split('\n')

    # Check if it looks like Markdown (has headers, lists, links, etc.)
    has_markdown_features = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for headers (#, ##, ###)
        if re.match(r'^#{1,6}\s+', line):
            has_markdown_features = True
            break

        # Check for list items (-, *, +, numbers)
        if re.match(r'^[\s]*[-\*\+]|\d+\.', line):
            has_markdown_features = True
            break

        # Check for links [text](url)
        if '[' in line and '](' in line and ')' in line:
            has_markdown_features = True
            break

        # Check for emphasis (*text*, **text**, _text_, __text__)
        if re.search(r'\*\*.*?\*\*|\*.*?\*|_{2}.*?_{2}|_.*?_', line):
            has_markdown_features = True
            break

    # If no Markdown features found, that's still OK - it could be plain text
    # that will be treated as Markdown
    if not has_markdown_features:
        logger.info("Markdown file appears to be plain text - this is acceptable")

    return True
