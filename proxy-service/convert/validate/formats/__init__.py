"""
Format-specific validators for file validation.
"""

# Import all validators to make them available
from . import html, pdf, docx, md, txt, json_validator, tex, xlsx

__all__ = ['html', 'pdf', 'docx', 'md', 'txt', 'json_validator', 'tex', 'xlsx']
