"""
TeX/LaTeX file validation.

Validates TeX and LaTeX files using content and structure checks.
"""

from pathlib import Path
from typing import Optional
import logging
import re

logger = logging.getLogger(__name__)

def validate_tex(file_path: str) -> bool:
    """
    Validate TeX/LaTeX file.

    Checks:
    - File can be read as UTF-8 text
    - Contains some content
    - Basic TeX/LaTeX structure (documentclass, begin/end document, etc.)

    Args:
        file_path: Path to the TeX file

    Returns:
        bool: True if validation passes

    Raises:
        ValueError: If validation fails
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='strict') as f:
            content = f.read()
    except UnicodeDecodeError:
        raise ValueError("TeX file must be valid UTF-8 encoded text")
    except Exception as e:
        raise ValueError(f"Failed to read TeX file: {e}")

    if not content.strip():
        raise ValueError("TeX file is empty")

    # Basic TeX/LaTeX validation
    lines = content.split('\n')

    # Check for documentclass (LaTeX) or basic TeX commands
    has_tex_commands = False
    has_document_structure = False

    for line in lines:
        line = line.strip()
        if not line or line.startswith('%'):
            continue

        # Check for LaTeX documentclass
        if re.search(r'\\documentclass', line):
            has_tex_commands = True
            has_document_structure = True
            break

        # Check for basic TeX commands
        if re.search(r'\\input|\\include|\\usepackage|\\begin|\\end', line):
            has_tex_commands = True

        # Check for document environment
        if re.search(r'\\begin{document}|\\end{document}', line):
            has_document_structure = True

    if not has_tex_commands:
        raise ValueError("TeX file must contain TeX commands (backslash commands)")

    if not has_document_structure:
        logger.warning("TeX file missing standard document structure (documentclass, begin/end document)")

    return True
