"""
Conversion configuration for the /convert endpoints.

This module defines the conversion pairs and their preferred services based on
quality, reliability, and format support analysis.
"""

from typing import Dict, List, Tuple, Optional
from enum import Enum


class ConversionService(Enum):
    """Available conversion services."""
    UNSTRUCTURED_IO = "unstructured-io"
    LIBREOFFICE = "libreoffice"
    PANDOC = "pandoc"
    GOTENBERG = "gotenberg"


class ConversionPriority(Enum):
    """Priority levels for conversion methods."""
    PRIMARY = "primary"      # Best quality/reliability
    SECONDARY = "secondary"  # Good alternative
    TERTIARY = "tertiary"    # Fallback option


# Conversion matrix defining input -> output format mappings with preferred services
CONVERSION_MATRIX = {
    # PDF Output Conversions (Gotenberg preferred for supported formats)
    ("html", "pdf"): [
        (ConversionService.GOTENBERG, ConversionPriority.PRIMARY, "High-fidelity HTML to PDF with CSS support"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "Good for simple HTML"),
        (ConversionService.LIBREOFFICE, ConversionPriority.TERTIARY, "Basic HTML support"),
    ],
    ("docx", "pdf"): [
        (ConversionService.GOTENBERG, ConversionPriority.PRIMARY, "High-quality office document to PDF"),
        (ConversionService.LIBREOFFICE, ConversionPriority.SECONDARY, "Excellent office format support"),
        (ConversionService.PANDOC, ConversionPriority.TERTIARY, "Limited office format support"),
    ],
    ("pptx", "pdf"): [
        (ConversionService.GOTENBERG, ConversionPriority.PRIMARY, "High-quality presentation to PDF"),
        (ConversionService.LIBREOFFICE, ConversionPriority.SECONDARY, "Excellent presentation support"),
    ],
    ("ppt", "pdf"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Legacy presentation format support"),
        (ConversionService.GOTENBERG, ConversionPriority.SECONDARY, "May work via LibreOffice"),
    ],
    ("xlsx", "pdf"): [
        (ConversionService.GOTENBERG, ConversionPriority.PRIMARY, "High-quality spreadsheet to PDF"),
        (ConversionService.LIBREOFFICE, ConversionPriority.SECONDARY, "Excellent spreadsheet support"),
    ],
    ("xls", "pdf"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Legacy spreadsheet format support"),
        (ConversionService.GOTENBERG, ConversionPriority.SECONDARY, "May work via LibreOffice"),
    ],
    ("odt", "pdf"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Native OpenDocument support"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "Good OpenDocument support"),
    ],
    ("ods", "pdf"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Native OpenDocument spreadsheet support"),
    ],
    ("odp", "pdf"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Native OpenDocument presentation support"),
    ],
    ("rtf", "pdf"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Good RTF support"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "Limited RTF support"),
    ],
    ("txt", "pdf"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Simple text to PDF"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "Text to PDF via LaTeX"),
    ],
    ("md", "pdf"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "Markdown to PDF via LaTeX"),
        (ConversionService.LIBREOFFICE, ConversionPriority.SECONDARY, "Basic markdown support"),
    ],
    ("tex", "pdf"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "LaTeX to PDF"),
    ],
    ("latex", "pdf"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "LaTeX to PDF"),
    ],
    ("epub", "pdf"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "E-book to PDF"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "E-book format support"),
    ],
    ("pages", "pdf"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Apple Pages to PDF via LibreOffice"),
    ],

    # JSON Output Conversions (Unstructured IO preferred)
    ("docx", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Document structure extraction"),
    ],
    ("pdf", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "PDF structure extraction"),
    ],
    ("pptx", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Presentation structure extraction"),
    ],
    ("ppt", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Legacy presentation structure extraction"),
    ],
    ("xlsx", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Spreadsheet structure extraction"),
    ],
    ("html", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "HTML structure extraction"),
    ],
    ("epub", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "E-book structure extraction"),
    ],
    ("rtf", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "RTF structure extraction"),
    ],
    ("txt", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Text structure extraction"),
    ],
    ("eml", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Email structure extraction"),
    ],
    ("msg", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "Outlook message structure extraction"),
    ],

    # URL Input Conversions
    ("url", "pdf"): [
        (ConversionService.GOTENBERG, ConversionPriority.PRIMARY, "URL to PDF conversion with full CSS support"),
    ],
    ("url", "json"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "URL content structure extraction"),
    ],
    ("url", "md"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "URL to markdown conversion"),
    ],
    ("url", "txt"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "URL to text conversion"),
    ],

    # DOCX Output Conversions
    ("md", "docx"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "Markdown to Word"),
        (ConversionService.LIBREOFFICE, ConversionPriority.SECONDARY, "Via intermediate format"),
    ],
    ("html", "docx"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "HTML to Word"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "HTML to Word"),
    ],
    ("pdf", "docx"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "PDF to Word (OCR-like)"),
    ],
    ("rtf", "docx"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "RTF to Word"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "Limited RTF support"),
    ],
    ("txt", "docx"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Text to Word"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "Text to Word"),
    ],
    ("odt", "docx"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "OpenDocument to Word"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "OpenDocument support"),
    ],
    ("pages", "docx"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Apple Pages to DOCX via LibreOffice")
    ],

    # Markdown Output Conversions (Pandoc preferred)
    ("docx", "md"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "Word to Markdown"),
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.SECONDARY, "Structure extraction only"),
    ],
    ("html", "md"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "HTML to Markdown"),
    ],
    ("pdf", "md"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "PDF to text structure"),
    ],
    ("tex", "md"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "LaTeX to Markdown"),
    ],
    ("latex", "md"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "LaTeX to Markdown"),
    ],
    ("rtf", "md"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "RTF to Markdown"),
    ],
    ("txt", "md"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "Text to Markdown"),
    ],
    ("epub", "md"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "E-book to Markdown"),
    ],

    # HTML Output Conversions
    ("docx", "html"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Word to HTML"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "Word to HTML"),
    ],
    ("pdf", "html"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "PDF to HTML"),
    ],
    ("md", "html"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "Markdown to HTML"),
    ],
    ("tex", "html"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "LaTeX to HTML"),
    ],
    ("latex", "html"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "LaTeX to HTML"),
    ],
    ("rtf", "html"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "RTF to HTML"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "Limited RTF support"),
    ],
    ("txt", "html"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Text to HTML"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "Text to HTML"),
    ],
    ("odt", "html"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "OpenDocument to HTML"),
        (ConversionService.PANDOC, ConversionPriority.SECONDARY, "OpenDocument support"),
    ],
    ("pages", "html"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Apple Pages to HTML via LibreOffice")
    ],

    # LaTeX Output Conversions (Pandoc preferred)
    ("md", "tex"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "Markdown to LaTeX"),
    ],
    ("html", "tex"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "HTML to LaTeX"),
    ],
    ("docx", "tex"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "Word to LaTeX"),
    ],
    ("txt", "tex"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "Text to LaTeX"),
    ],

    # Text Output Conversions
    ("docx", "txt"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Word to Text"),
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.SECONDARY, "Text extraction"),
        (ConversionService.PANDOC, ConversionPriority.TERTIARY, "Word to Text"),
    ],
    ("pdf", "txt"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "PDF text extraction"),
        (ConversionService.LIBREOFFICE, ConversionPriority.SECONDARY, "PDF to Text"),
    ],
    ("html", "txt"): [
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.PRIMARY, "HTML text extraction"),
        (ConversionService.LIBREOFFICE, ConversionPriority.SECONDARY, "HTML to Text"),
        (ConversionService.PANDOC, ConversionPriority.TERTIARY, "HTML to Text"),
    ],
    ("md", "txt"): [
        (ConversionService.PANDOC, ConversionPriority.PRIMARY, "Markdown to Text"),
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.SECONDARY, "Text extraction"),
    ],
    ("rtf", "txt"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "RTF to Text"),
        (ConversionService.UNSTRUCTURED_IO, ConversionPriority.SECONDARY, "Text extraction"),
    ],
    ("pages", "txt"): [
        (ConversionService.LIBREOFFICE, ConversionPriority.PRIMARY, "Apple Pages to TXT via LibreOffice")
    ],
}


def get_conversion_methods(input_format: str, output_format: str) -> List[Tuple[ConversionService, ConversionPriority, str]]:
    """
    Get available conversion methods for a given input/output format pair.

    Args:
        input_format: Input file format (e.g., 'docx', 'pdf')
        output_format: Output file format (e.g., 'pdf', 'json')

    Returns:
        List of tuples containing (service, priority, description)
    """
    key = (input_format.lower(), output_format.lower())
    return CONVERSION_MATRIX.get(key, [])


def get_primary_conversion(input_format: str, output_format: str) -> Optional[Tuple[ConversionService, str]]:
    """
    Get the primary (highest quality) conversion method for a format pair.

    Args:
        input_format: Input file format
        output_format: Output file format

    Returns:
        Tuple of (service, description) or None if no conversion available
    """
    methods = get_conversion_methods(input_format, output_format)
    if not methods:
        return None

    # Return the highest priority method
    primary_methods = [m for m in methods if m[1] == ConversionPriority.PRIMARY]
    if primary_methods:
        service, _, description = primary_methods[0]
        return (service, description)

    # Fallback to any available method
    service, _, description = methods[0]
    return (service, description)


def get_supported_conversions() -> Dict[str, List[str]]:
    """
    Get all supported input formats and their possible output formats.

    Returns:
        Dictionary mapping input formats to lists of output formats
    """
    supported = {}
    for (input_fmt, output_fmt), _ in CONVERSION_MATRIX.items():
        if input_fmt not in supported:
            supported[input_fmt] = []
        if output_fmt not in supported[input_fmt]:
            supported[input_fmt].append(output_fmt)

    return supported


# All supported format pairs for reference
ALL_SUPPORTED_CONVERSIONS = list(CONVERSION_MATRIX.keys())
