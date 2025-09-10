"""
Format-specific validators for file validation.
"""

# Import all validators to make them available
from . import html, pdf, docx, md, txt, json, tex, xlsx, pptx, odt, ods, odp

__all__ = ['html', 'pdf', 'docx', 'md', 'txt', 'json', 'tex', 'xlsx', 'pptx', 'odt', 'ods', 'odp']
